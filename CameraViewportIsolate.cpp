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
    std::atomic<std::uint64_t> g_targetCameraHandle{0};
    std::atomic<bool> g_active{false};
    std::atomic<std::uint64_t> g_suppressed{0};
    std::atomic<std::uint64_t> g_exCalls{0};
    std::atomic<std::uint64_t> g_lastSeenCamera{0};

    INodeDisplayControl* g_control = nullptr;
    NodeDisplayCallback* g_previous = nullptr;
    bool g_registered = false;

    class CameraSpecificDisplayCallback final : public NodeDisplayCallbackEx
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

        void StartDisplay(TimeValue, ViewExp*, int) override {}
        void EndDisplay(TimeValue, ViewExp*, int) override {}

        bool Display(TimeValue, ViewExp*, int, INode*, Object*) override
        {
            return false;
        }

        // Never use the scene-wide legacy overload for hiding.
        bool SuspendObjectDisplay(TimeValue, INode*) override
        {
            return false;
        }

        // Camera-specific path. The same camera can be placed in any viewport;
        // isolation follows the CAMERA NODE, not the viewport slot/index.
        bool SuspendObjectDisplay(TimeValue, ViewExp* vpt, INode* node, Object*) override
        {
            g_exCalls.fetch_add(1, std::memory_order_relaxed);

            if (!g_active.load(std::memory_order_acquire))
                return false;

            if (vpt == nullptr || node == nullptr || node->IsRootNode())
                return false;

            INode* viewCamera = vpt->GetViewCamera();
            if (viewCamera == nullptr)
            {
                g_lastSeenCamera.store(0, std::memory_order_relaxed);
                return false;
            }

            const auto cameraHandle = static_cast<std::uint64_t>(
                Animatable::GetHandleByAnim(viewCamera));
            g_lastSeenCamera.store(cameraHandle, std::memory_order_relaxed);

            if (cameraHandle != g_targetCameraHandle.load(std::memory_order_relaxed))
                return false;

            const auto handles = std::atomic_load_explicit(
                &g_visibleHandles, std::memory_order_acquire);
            const auto nodeHandle = static_cast<std::uint64_t>(
                Animatable::GetHandleByAnim(node));

            const bool hideInThisCamera = handles->find(nodeHandle) == handles->end();
            if (hideInThisCamera)
                g_suppressed.fetch_add(1, std::memory_order_relaxed);

            return hideInThisCamera;
        }

        void AddNodeCallbackBox(TimeValue, INode*, ViewExp*, Box3&, Object*) override {}

        bool HitTest(TimeValue, INode*, int, int, int, IPoint2*, ViewExp*, Object*) override
        {
            return false;
        }

        void Activate() override
        {
            if (auto* c = GetNodeDisplayControl(GetCOREInterface()))
                c->InvalidateNodeDisplay();
        }

        void Deactivate() override
        {
            if (auto* c = GetNodeDisplayControl(GetCOREInterface()))
                c->InvalidateNodeDisplay();
        }

        MSTR GetName() const override
        {
            return MSTR(L"Camera Specific Viewport Isolate");
        }
    };

    CameraSpecificDisplayCallback g_callback;

    INodeDisplayControl* Control()
    {
        if (g_control == nullptr)
            g_control = GetNodeDisplayControl(GetCOREInterface());
        return g_control;
    }

    void Invalidate()
    {
        if (auto* c = Control())
            c->InvalidateNodeDisplay();
        if (auto* ip = GetCOREInterface())
            ip->RedrawViews(ip->GetTime());
    }

    int TakeControl()
    {
        auto* c = Control();
        if (c == nullptr)
            return -2;

        NodeDisplayCallback* current = c->GetNodeCallback();

        if (current != &g_callback)
        {
            // Save whatever Max/plugin currently owns the slot. We temporarily
            // replace it only while camera isolation is active, then restore it.
            g_previous = current;
        }

        if (!g_registered)
        {
            c->RegisterNodeDisplayCallback(&g_callback);
            g_registered = true;
        }

        if (c->GetNodeCallback() != &g_callback)
        {
            if (!c->SetNodeCallback(&g_callback))
                return -3;
        }

        return 1;
    }

    void RestorePreviousCallback()
    {
        auto* c = Control();
        if (c == nullptr)
            return;

        if (c->GetNodeCallback() == &g_callback)
            c->SetNodeCallback(g_previous);

        g_previous = nullptr;
    }
}

extern "C"
{
    __declspec(dllexport)
    int CameraVP_Isolate(
        std::uint64_t cameraHandle,
        const std::uint64_t* visibleHandles,
        int handleCount)
    {
        if (cameraHandle == 0 || visibleHandles == nullptr || handleCount <= 0)
            return -1;

        const int controlResult = TakeControl();
        if (controlResult != 1)
            return controlResult;

        auto next = std::make_shared<HandleSet>();
        next->reserve(static_cast<std::size_t>(handleCount));
        for (int i = 0; i < handleCount; ++i)
            next->insert(visibleHandles[i]);

        std::atomic_store_explicit(
            &g_visibleHandles,
            std::static_pointer_cast<const HandleSet>(next),
            std::memory_order_release);

        g_targetCameraHandle.store(cameraHandle, std::memory_order_relaxed);
        g_suppressed.store(0, std::memory_order_relaxed);
        g_exCalls.store(0, std::memory_order_relaxed);
        g_lastSeenCamera.store(0, std::memory_order_relaxed);
        g_active.store(true, std::memory_order_release);

        Invalidate();
        return 1;
    }

    __declspec(dllexport)
    int CameraVP_Restore()
    {
        g_active.store(false, std::memory_order_release);
        g_targetCameraHandle.store(0, std::memory_order_relaxed);
        std::atomic_store_explicit(
            &g_visibleHandles,
            std::make_shared<const HandleSet>(),
            std::memory_order_release);

        RestorePreviousCallback();
        Invalidate();
        return 1;
    }

    __declspec(dllexport)
    int CameraVP_IsActive()
    {
        return g_active.load(std::memory_order_acquire) ? 1 : 0;
    }

    __declspec(dllexport)
    std::uint64_t CameraVP_TargetCamera()
    {
        return g_targetCameraHandle.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraVP_LastSeenCamera()
    {
        return g_lastSeenCamera.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraVP_SuppressedCount()
    {
        return g_suppressed.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraVP_ExCallCount()
    {
        return g_exCalls.load(std::memory_order_relaxed);
    }
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID)
{
    return TRUE;
}
