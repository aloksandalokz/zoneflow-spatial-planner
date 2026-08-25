/* AOPR 50_Tests.ms */

fn AOPR_TestResult name ok detail =
(
    local prefix = if ok then "PASS" else "FAIL"
    AOPR_Log (prefix + " | " + name + " | " + detail)
    ok
)

fn AOPR_Test_Geometry =
(
    local b = box length:200 width:400 height:50 pos:[0,0,0]
    local cam = freeCamera()
    local r = AOPR_SetCameraDirection cam b #top
    local w = undefined
    if r[1] do
    (
        AOPR_CenterCameraOnObject cam b
        w = AOPR_ProjectedWidth cam b
    )
    local ok = r[1] and (w != undefined) and (abs(w - 400.0) < 0.01)
    delete cam
    delete b
    AOPR_TestResult "Geometry/top projected width" ok ("width=" + (w as string))
)

fn AOPR_Test_CoronaCreate =
(
    local cam = AOPR_CreateCoronaCamera "AOPR_TEST_CORONA"
    local ok = AOPR_IsValidNode cam
    local detail = if ok then ((classOf cam) as string) else "CoronaCam() failed"
    if ok do delete cam
    AOPR_TestResult "Corona camera creation" ok detail
)

fn AOPR_Test_CoronaOrtho =
(
    local cam = AOPR_CreateCoronaCamera "AOPR_TEST_ORTHO"
    if not (AOPR_IsValidNode cam) then AOPR_TestResult "Corona orthographic" false "camera creation failed"
    else
    (
        local ok = AOPR_DiscoverOrthographicProjection cam
        local detail = "prop=" + (AOPR_CORONA_PROJECTION_PROP as string) + " value=" + (AOPR_CORONA_ORTHO_VALUE as string)
        delete cam
        AOPR_TestResult "Corona orthographic" ok detail
    )
)

fn AOPR_Test_CoronaSize =
(
    local cam = AOPR_CreateCoronaCamera "AOPR_TEST_SIZE"
    if not (AOPR_IsValidNode cam) then AOPR_TestResult "Corona ortho size" false "camera creation failed"
    else
    (
        local p = AOPR_DiscoverOrthoSizeProperty cam
        local ok = p != undefined
        local detail = "prop=" + (p as string)
        delete cam
        AOPR_TestResult "Corona ortho size" ok detail
    )
)

fn AOPR_RunAllTests =
(
    AOPR_Log_Reset()
    AOPR_Log ("AOPR tests - " + AOPR_VERSION)
    AOPR_Test_Geometry()
    AOPR_Test_CoronaCreate()
    AOPR_Test_CoronaOrtho()
    AOPR_Test_CoronaSize()
    AOPR_Log "Tests complete."
    AOPR_LOG_LINES
)
