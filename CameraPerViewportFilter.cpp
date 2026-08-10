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
#include <maxapi.h>

#include <atomic>
#include <cstdint>
#include <memory>
#include <unordered_set>

#include "CameraPerViewportFilterLogic.h"

using CameraPerViewportFilterLogic::Handle;
using CameraPerViewportFilterLogic::HandleSet;

namespace
{
    std::shared_ptr<const HandleSet> g_visibleHandles = std::make_shared<const HandleSet>();
    std::atomic<Handle> g_targetCamera{0};
    std::atomic<Handle> g_currentViewportCamera{0};
    std::atomic<Handle> g_lastSeenCamera{0};
    std::atomic<bool> g_active{false};

    std::atomic<std::uint64_t> g_preCalls{0};
    std::atomic<std::uint64_t> g_postCalls{0};
    std::atomic<std::uint64_t> g_filterCalls{0};
    std::atomic<std::uint64_t> g_hiddenDecisions{0};

    bool g_registered = false;

    Handle HandleOf(INode* node)
    {
        if (node == nullptr) return 0;
        return static_cast<Handle>(Animatable::GetHandleByAnim(node));
    }

    class CameraContextCallback final : public ViewportDisplayCallback
    {
    public:
        explicit CameraContextCallback(bool pre) : m_pre(pre) {}

        void Display(TimeValue, ViewExp* vpt, int) override
        {
            if (m_pre)
            {
                g_preCalls.fetch_add(1, std::memory_order_relaxed);
                const Handle camera = (vpt != nullptr) ? HandleOf(vpt->GetViewCamera()) : 0;
                g_currentViewportCamera.store(camera, std::memory_order_release);
                g_lastSeenCamera.store(camera, std::memory_order_relaxed);
            }
            else
            {
                g_postCalls.fetch_add(1, std::memory_order_relaxed);
                g_currentViewportCamera.store(0, std::memory_order_release);
            }
        }

        void GetViewportRect(TimeValue, ViewExp* vpt, Rect* rect) override
        {
            if (rect == nullptr) return;
            if (vpt != nullptr)
                *rect = vpt->GetDammageRect();
            else
                *rect = Rect(0, 0, 0, 0);
        }

        BOOL Foreground() override
        {
            return TRUE;
        }

    private:
        bool m_pre;
    };

    class CameraSelectionDisplayFilter final : public DisplayFilterCallback
    {
    public:
        CameraSelectionDisplayFilter()
        {
            on = TRUE;
        }

        const MCHAR* GetName() override
        {
            return _T("Camera Selected Only");
        }

        BOOL IsHidden(SClass_ID, Class_ID, INode* node) override
        {
            g_filterCalls.fetch_add(1, std::memory_order_relaxed);

            if (node == nullptr || node->IsRootNode())
                return FALSE;

            const auto visible = std::atomic_load_explicit(
                &g_visibleHandles, std::memory_order_acquire);

            const bool hide = CameraPerViewportFilterLogic::ShouldHide(
                g_active.load(std::memory_order_acquire),
                g_targetCamera.load(std::memory_order_relaxed),
                g_currentViewportCamera.load(std::memory_order_acquire),
                HandleOf(node),
                *visible);

            if (hide)
                g_hiddenDecisions.fetch_add(1, std::memory_order_relaxed);

            return hide ? TRUE : FALSE;
        }
    };

    CameraContextCallback g_preCallback(true);
    CameraContextCallback g_postCallback(false);
    CameraSelectionDisplayFilter g_displayFilter;

    void ResetDiagnostics()
    {
        g_preCalls.store(0, std::memory_order_relaxed);
        g_postCalls.store(0, std::memory_order_relaxed);
        g_filterCalls.store(0, std::memory_order_relaxed);
        g_hiddenDecisions.store(0, std::memory_order_relaxed);
        g_lastSeenCamera.store(0, std::memory_order_relaxed);
    }

    void ForceRedraw()
    {
        if (auto* ip = GetCOREInterface())
        {
            if (g_registered)
            {
                ip->NotifyViewportDisplayCallbackChanged(TRUE, &g_preCallback);
                ip->NotifyViewportDisplayCallbackChanged(FALSE, &g_postCallback);
            }
            ip->RedrawViews(ip->GetTime());
        }
    }

    int EnsureRegistered()
    {
        if (g_registered)
        {
            g_displayFilter.on = TRUE;
            return 1;
        }

        auto* ip = GetCOREInterface();
        if (ip == nullptr)
            return -2;

        ip->RegisterDisplayFilterCallback(&g_displayFilter);
        g_displayFilter.on = TRUE;
        ip->RegisterViewportDisplayCallback(TRUE, &g_preCallback);
        ip->RegisterViewportDisplayCallback(FALSE, &g_postCallback);

        g_registered = true;
        return 1;
    }

    void UnregisterCallbacks()
    {
        if (!g_registered)
            return;

        if (auto* ip = GetCOREInterface())
        {
            ip->UnRegisterViewportDisplayCallback(TRUE, &g_preCallback);
            ip->UnRegisterViewportDisplayCallback(FALSE, &g_postCallback);
            ip->UnRegisterDisplayFilterCallback(&g_displayFilter);
        }
        g_registered = false;
    }
}

extern "C"
{
    __declspec(dllexport)
    int CameraFilter_Isolate(
        std::uint64_t cameraHandle,
        const std::uint64_t* visibleHandles,
        int handleCount)
    {
        if (cameraHandle == 0 || visibleHandles == nullptr || handleCount <= 0)
            return -1;

        const int registration = EnsureRegistered();
        if (registration != 1)
            return registration;

        auto next = std::make_shared<HandleSet>();
        next->reserve(static_cast<std::size_t>(handleCount));
        for (int i = 0; i < handleCount; ++i)
            next->insert(visibleHandles[i]);

        std::atomic_store_explicit(
            &g_visibleHandles,
            std::static_pointer_cast<const HandleSet>(next),
            std::memory_order_release);

        g_targetCamera.store(cameraHandle, std::memory_order_relaxed);
        g_currentViewportCamera.store(0, std::memory_order_relaxed);
        g_active.store(true, std::memory_order_release);
        ResetDiagnostics();
        ForceRedraw();
        return 1;
    }

    __declspec(dllexport)
    int CameraFilter_Restore()
    {
        g_active.store(false, std::memory_order_release);
        g_targetCamera.store(0, std::memory_order_relaxed);
        g_currentViewportCamera.store(0, std::memory_order_relaxed);
        std::atomic_store_explicit(
            &g_visibleHandles,
            std::make_shared<const HandleSet>(),
            std::memory_order_release);
        ForceRedraw();
        return 1;
    }

    __declspec(dllexport)
    int CameraFilter_Shutdown()
    {
        CameraFilter_Restore();
        UnregisterCallbacks();
        return 1;
    }

    __declspec(dllexport)
    int CameraFilter_IsActive()
    {
        return g_active.load(std::memory_order_acquire) ? 1 : 0;
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_TargetCamera()
    {
        return g_targetCamera.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_LastSeenCamera()
    {
        return g_lastSeenCamera.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_PreCalls()
    {
        return g_preCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_PostCalls()
    {
        return g_postCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_FilterCalls()
    {
        return g_filterCalls.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    std::uint64_t CameraFilter_HiddenDecisions()
    {
        return g_hiddenDecisions.load(std::memory_order_relaxed);
    }

    __declspec(dllexport)
    int CameraFilter_SelfTest()
    {
        using CameraPerViewportFilterLogic::ShouldHide;
        const HandleSet visible{10, 20};
        if (ShouldHide(false, 100, 100, 30, visible)) return 0;
        if (ShouldHide(true, 100, 200, 30, visible)) return 0;
        if (ShouldHide(true, 100, 100, 10, visible)) return 0;
        if (!ShouldHide(true, 100, 100, 30, visible)) return 0;
        return 1;
    }
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID)
{
    return TRUE;
}
