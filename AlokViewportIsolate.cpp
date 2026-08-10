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

    // Runtime diagnostics. These let the Python palette prove that 3ds Max is
    // actually calling the viewport-aware callback rather than the legacy one.
    std::atomic<std::uint64_t> g_exCalls{0};
    std::atomic<std::uint64_t> g_legacyCalls{0};
    std::atomic<std::uint64_t> g_suppressedCalls{0};
    std::atomic<int> g_lastSeenViewID{-1};

    INodeDisplayControl* g_displayControl = nullptr;
    bool g_registered = false;

    class AlokViewportDisplayCallback final : public NodeDisplayCallbackEx
    {
    public:
        // CRITICAL: BaseInterface::GetInterface() returns NULL by default.
        // 3ds Max asks the callback for IID_NODE_DISPLAY_CALLBACK_EX before it
        // will call the overload that contains ViewExp*. Return the direct
        // BaseInterface subobject for that ID so Max can discover Ex support.
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

        void StartDisplay(TimeValue, ViewExp*, int) override {}
        void EndDisplay(TimeValue, ViewExp*, int) override {}

        bool Display(TimeValue, ViewExp*, int, INode*, Object*) override
        {
            // We do not draw replacement geometry. Normal drawing is controlled
            // by SuspendObjectDisplay().
            return false;
        }

        // Legacy path has no viewport context. Never suppress here because doing
        // so would hide objects in every viewport.
        bool SuspendObjectDisplay(TimeValue, INode*) override
        {
            g_legacyCalls.fetch_add(1, std::memory_order_relaxed);
            return false;
        }

        // Viewport-aware path. Only the target viewport is affected.
        bool SuspendObjectDisplay(TimeValue, ViewExp* vpt, INode* node, Object*) override
        {
            g_exCalls.fetch_add(1, std::memory_order_relaxed);

            if (vpt != nullptr)
                g_lastSeenViewID.store(vpt->GetViewID(), std::memory_order_relaxed);

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

            const bool suppress = handles->find(nodeHandle) == handles->end();
            if (suppress)
                g_suppressedCalls.fetch_add(1, std::memory_order_relaxed);

            return suppress;
        }

        void AddNodeCallbackBox(TimeValue, INode*, ViewExp*, Box3&, Object*) override {}

        bool HitTest(
            TimeValue, INode*, int, int, int, IPoint2*, ViewExp*, Object*) override
        {
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

        // Do not steal the global display hook from another active utility.
        if (current != nullptr && current != &g_callback)
            return -3;

        if (!g_registered)
        {
            control->RegisterNodeDisplayCallback(&g_callback);
            g_registered = true;
        }

        if (control->GetNodeCallback() != &g_callback)
        {
            if (!control->SetNodeCallback(&g_callback))
                return -4;
        }

        return 1;
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
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID)
{
    return TRUE;
}
