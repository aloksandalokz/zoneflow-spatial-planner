#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <max.h>
#include <nodedisp.h>

#include <atomic>
#include <cstdint>
#include <memory>
#include <unordered_set>

using HandleSet = std::unordered_set<std::uint64_t>;

namespace
{
    std::shared_ptr<const HandleSet> g_visibleHandles = std::make_shared<const HandleSet>();
    std::atomic<int>  g_targetViewID{-1};
    std::atomic<bool> g_isolationActive{false};

    std::atomic<std::uint64_t> g_exCalls{0};
    std::atomic<std::uint64_t> g_legacyCalls{0};
    std::atomic<std::uint64_t> g_suppressedCalls{0};
    std::atomic<int> g_lastSeenViewID{-1};

    INodeDisplayControl* g_displayControl = nullptr;
    NodeDisplayCallback* g_previousCallback = nullptr;
    bool g_registered = false;

    bool IsSuppressedInTargetViewport(ViewExp* vpt, INode* node)
    {
        if (!g_isolationActive.load(std::memory_order_acquire))
            return false;

        if (vpt == nullptr || node == nullptr || node->IsRootNode())
            return false;

        if (vpt->GetViewID() != g_targetViewID.load(std::memory_order_relaxed))
            return false;

        const auto handles = std::atomic_load_explicit(
            &g_visibleHandles, std::memory_order_acquire);

        const auto nodeHandle =
            static_cast<std::uint64_t>(Animatable::GetHandleByAnim(node));

        return handles->find(nodeHandle) == handles->end();
    }

    class AlokViewportDisplayCallback final : public NodeDisplayCallbackEx
    {
    public:
        BaseInterface* GetInterface(Interface_ID id) override
        {
            if (id == IID_NODE_DISPLAY_CALLBACK_EX)
                return static_cast<BaseInterface*>(this);
            return nullptr;
        }

        Interface_ID GetID() override
        {
            return IID_NODE_DISPLAY_CALLBACK_EX;
        }

        LifetimeType LifetimeControl() override
        {
            return noRelease;
        }

        void StartDisplay(TimeValue t, ViewExp* vpt, int flags) override
        {
            if (g_previousCallback != nullptr)
                g_previousCallback->StartDisplay(t, vpt, flags);
        }

        void EndDisplay(TimeValue t, ViewExp* vpt, int flags) override
        {
            if (g_previousCallback != nullptr)
                g_previousCallback->EndDisplay(t, vpt, flags);
        }

        bool Display(TimeValue t, ViewExp* vpt, int flags, INode* node, Object* pObj) override
        {
            if (IsSuppressedInTargetViewport(vpt, node))
                return false;

            if (g_previousCallback != nullptr)
                return g_previousCallback->Display(t, vpt, flags, node, pObj);

            return false;
        }

        bool SuspendObjectDisplay(TimeValue t, INode* node) override
        {
            g_legacyCalls.fetch_add(1, std::memory_order_relaxed);

            // No viewport context is available here, so this tool itself never
            // suppresses via the legacy path. Preserve any pre-existing callback.
            if (g_previousCallback != nullptr)
                return g_previousCallback->SuspendObjectDisplay(t, node);

            return false;
        }

        bool SuspendObjectDisplay(TimeValue t, ViewExp* vpt, INode* node, Object* pObj) override
        {
            g_exCalls.fetch_add(1, std::memory_order_relaxed);

            if (vpt != nullptr)
                g_lastSeenViewID.store(vpt->GetViewID(), std::memory_order_relaxed);

            bool previousSuppress = false;
            if (g_previousCallback != nullptr)
            {
                // Preserve the existing callback's normal suppression behavior.
                // The base callback API exposes the legacy decision reliably;
                // our own per-viewport decision is added on top of it.
                previousSuppress = g_previousCallback->SuspendObjectDisplay(t, node);
            }

            const bool ourSuppress = IsSuppressedInTargetViewport(vpt, node);
            if (ourSuppress)
                g_suppressedCalls.fetch_add(1, std::memory_order_relaxed);

            return previousSuppress || ourSuppress;
        }

        void AddNodeCallbackBox(TimeValue t, INode* node, ViewExp* vpt, Box3& box, Object* pObj) override
        {
            if (g_previousCallback != nullptr && !IsSuppressedInTargetViewport(vpt, node))
                g_previousCallback->AddNodeCallbackBox(t, node, vpt, box, pObj);
        }

        bool HitTest(
            TimeValue t, INode* node, int type, int crossing, int flags,
            IPoint2* p, ViewExp* vpt, Object* pObj) override
        {
            if (IsSuppressedInTargetViewport(vpt, node))
                return false;

            if (g_previousCallback != nullptr)
                return g_previousCallback->HitTest(
                    t, node, type, crossing, flags, p, vpt, pObj);

            return false;
        }

        void Activate() override
        {
            InvalidateDisplay();
        }

        void Deactivate() override
        {
            InvalidateDisplay();
        }

        MSTR GetName() const override
        {
            return MSTR(L"Alok - Isolate This Viewport");
        }

    private:
        static void InvalidateDisplay()
        {
            if (auto* control = GetNodeDisplayControl(GetCOREInterface()))
                control->InvalidateNodeDisplay();
        }
    };

    AlokViewportDisplayCallback g_callback;

    INodeDisplayControl* GetDisplayControl()
    {
        if (g_displayControl == nullptr)
            g_displayControl = GetNodeDisplayControl(GetCOREInterface());
        return g_displayControl;
    }

    void InvalidateDisplay()
    {
        if (auto* control = GetDisplayControl())
            control->InvalidateNodeDisplay();
    }

    void ResetDiagnostics()
    {
        g_exCalls.store(0, std::memory_order_relaxed);
        g_legacyCalls.store(0, std::memory_order_relaxed);
        g_suppressedCalls.store(0, std::memory_order_relaxed);
        g_lastSeenViewID.store(-1, std::memory_order_relaxed);
    }

    int EnsureCallbackIsCurrent()
    {
        auto* control = GetDisplayControl();
        if (control == nullptr)
            return -2;

        NodeDisplayCallback* current = control->GetNodeCallback();

        if (current != &g_callback)
        {
            // Remember whatever Max / another utility is currently using.
            // We forward its drawing behavior while isolated and restore it later.
            g_previousCallback = current;

            if (!g_registered)
            {
                control->RegisterNodeDisplayCallback(&g_callback);
                g_registered = true;
            }

            if (!control->SetNodeCallback(&g_callback))
                return -4;
        }

        return 1;
    }

    void RestorePreviousCallback()
    {
        auto* control = GetDisplayControl();
        if (control == nullptr)
            return;

        if (control->GetNodeCallback() == &g_callback)
        {
            // Restore the callback that was active before this tool took control.
            // Passing nullptr is valid for returning to no active callback.
            control->SetNodeCallback(g_previousCallback);
        }

        g_previousCallback = nullptr;
    }
}

extern "C"
{
    __declspec(dllexport)
    int AlokVP_Isolate(
        int viewID,
        const std::uint64_t* handles,
        int handleCount)
    {
        if (viewID < 0 || handles == nullptr || handleCount <= 0)
            return -1;

        const int callbackResult = EnsureCallbackIsCurrent();
        if (callbackResult != 1)
            return callbackResult;

        auto nextHandles = std::make_shared<HandleSet>();
        nextHandles->reserve(static_cast<std::size_t>(handleCount));

        for (int i = 0; i < handleCount; ++i)
            nextHandles->insert(handles[i]);

        std::atomic_store_explicit(
            &g_visibleHandles,
            std::static_pointer_cast<const HandleSet>(nextHandles),
            std::memory_order_release);

        g_targetViewID.store(viewID, std::memory_order_relaxed);
        g_isolationActive.store(true, std::memory_order_release);
        ResetDiagnostics();

        InvalidateDisplay();
        return 1;
    }

    __declspec(dllexport)
    int AlokVP_Restore()
    {
        g_isolationActive.store(false, std::memory_order_release);
        g_targetViewID.store(-1, std::memory_order_relaxed);

        std::atomic_store_explicit(
            &g_visibleHandles,
            std::make_shared<const HandleSet>(),
            std::memory_order_release);

        RestorePreviousCallback();
        InvalidateDisplay();
        return 1;
    }

    __declspec(dllexport)
    int AlokVP_IsActive()
    {
        return g_isolationActive.load(std::memory_order_acquire) ? 1 : 0;
    }

    __declspec(dllexport)
    int AlokVP_TargetViewID()
    {
        return g_targetViewID.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t AlokVP_ExCallCount()
    {
        return g_exCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t AlokVP_LegacyCallCount()
    {
        return g_legacyCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t AlokVP_SuppressedCount()
    {
        return g_suppressedCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    int AlokVP_LastSeenViewID()
    {
        return g_lastSeenViewID.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    int AlokVP_HasPreviousCallback()
    {
        return g_previousCallback != nullptr ? 1 : 0;
    }
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID)
{
    return TRUE;
}
