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

    INodeDisplayControl* g_displayControl = nullptr;
    bool g_registered = false;

    class AlokViewportDisplayCallback final : public NodeDisplayCallbackEx
    {
    public:
        BaseInterface* GetInterface(Interface_ID id) override
        {
            if (id == IID_NODE_DISPLAY_CALLBACK_EX)
                return static_cast<NodeDisplayCallbackEx*>(this);
            return NodeDisplayCallbackEx::GetInterface(id);
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
            return false;
        }

        bool SuspendObjectDisplay(TimeValue, INode*) override
        {
            return false;
        }

        bool SuspendObjectDisplay(TimeValue, ViewExp* vpt, INode* node, Object*) override
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

        void AddNodeCallbackBox(TimeValue, INode*, ViewExp*, Box3&, Object*) override {}

        bool HitTest(
            TimeValue, INode*, int, int, int, IPoint2*, ViewExp*, Object*) override
        {
            return false;
        }

        void Activate() override {}
        void Deactivate() override {}

        MSTR GetName() const override
        {
            return MSTR(_T("Alok - Isolate This Viewport"));
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

    int EnsureCallbackIsCurrent()
    {
        auto* control = GetDisplayControl();
        if (control == nullptr)
            return -2;

        NodeDisplayCallback* current = control->GetNodeCallback();

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
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID)
{
    return TRUE;
}
