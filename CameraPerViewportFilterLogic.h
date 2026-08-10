#pragma once
#include <cstdint>
#include <unordered_set>

namespace CameraPerViewportFilterLogic
{
    using Handle = std::uint64_t;
    using HandleSet = std::unordered_set<Handle>;

    inline bool ShouldHide(
        bool active,
        Handle targetCamera,
        Handle currentCamera,
        Handle nodeHandle,
        const HandleSet& visibleHandles)
    {
        if (!active) return false;
        if (targetCamera == 0 || currentCamera == 0) return false;
        if (currentCamera != targetCamera) return false;
        return visibleHandles.find(nodeHandle) == visibleHandles.end();
    }
}
