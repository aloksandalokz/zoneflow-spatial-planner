#include "CameraPerViewportFilterLogic.h"
#include <cstdlib>
#include <iostream>

using namespace CameraPerViewportFilterLogic;

static void require(bool cond, const char* msg)
{
    if (!cond)
    {
        std::cerr << "FAIL: " << msg << "\n";
        std::exit(1);
    }
}

int main()
{
    const Handle camA = 100;
    const Handle camB = 200;
    const Handle keep1 = 10;
    const Handle keep2 = 20;
    const Handle other = 30;
    HandleSet visible{keep1, keep2};

    require(!ShouldHide(false, camA, camA, other, visible),
        "inactive filter must never hide");
    require(!ShouldHide(true, camA, camB, other, visible),
        "Camera B must remain full scene");
    require(!ShouldHide(true, camA, 0, other, visible),
        "non-camera viewport must remain full scene");
    require(!ShouldHide(true, camA, camA, keep1, visible),
        "selected object 1 must remain visible in Camera A");
    require(!ShouldHide(true, camA, camA, keep2, visible),
        "selected object 2 must remain visible in Camera A");
    require(ShouldHide(true, camA, camA, other, visible),
        "unselected object must be hidden in Camera A");

    std::cout << "PASS: camera-specific viewport filter logic\n";
    return 0;
}
