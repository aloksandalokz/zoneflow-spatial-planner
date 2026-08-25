/* AOPR v4 standalone geometry test. No Corona dependency. */

global AOPR_GREEN = color 0 255 0
fn AOPR_IsValidNode n = ((n != undefined) and (isValidNode n))
fn AOPR_BBoxWorld obj = (local bb = undefined; if AOPR_IsValidNode obj do try(bb = nodeGetBoundingBox obj (matrix3 1))catch(); bb)
fn AOPR_BBoxInCamera obj cam = (local bb = undefined; if (AOPR_IsValidNode obj) and (AOPR_IsValidNode cam) do try(bb = nodeGetBoundingBox obj cam.transform)catch(); bb)
fn AOPR_WorldCenter obj = (local bb=AOPR_BBoxWorld obj; if bb==undefined then undefined else (bb[1]+bb[2])/2.0)
fn AOPR_WorldMaxDimension obj = (local bb=AOPR_BBoxWorld obj; if bb==undefined then undefined else (local e=bb[2]-bb[1]; max (abs e.x) (max (abs e.y) (abs e.z))))
fn AOPR_MakeCameraTM center viewDir upDir distance = (local forward=normalize viewDir; local zAxis=normalize(-forward); local xAxis=normalize(cross upDir zAxis); local yAxis=normalize(cross zAxis xAxis); local pos=center-(forward*distance); matrix3 xAxis yAxis zAxis pos)
fn AOPR_SetTopCamera cam obj = (local center=AOPR_WorldCenter obj; local d=AOPR_WorldMaxDimension obj; if (d==undefined) or (d<1.0) do d=100.0; cam.transform=AOPR_MakeCameraTM center [0,0,-1] [0,1,0] ((d*2.0)+100.0); true)
fn AOPR_CenterCameraOnObject cam obj = (local bb=AOPR_BBoxInCamera obj cam; if bb==undefined then false else (local cx=(bb[1].x+bb[2].x)/2.0; local cy=(bb[1].y+bb[2].y)/2.0; local tm=cam.transform; cam.pos=cam.pos+(tm.row1*cx)+(tm.row2*cy); true))
fn AOPR_ProjectedWidth cam obj = (local bb=AOPR_BBoxInCamera obj cam; if bb==undefined then undefined else abs(bb[2].x-bb[1].x))

local testBox = undefined
local testCam = undefined
local ok = false
local detail = ""
try
(
    testBox = box length:200 width:400 height:50 pos:[0,0,0]
    testCam = freeCamera()
    AOPR_SetTopCamera testCam testBox
    AOPR_CenterCameraOnObject testCam testBox
    local w = AOPR_ProjectedWidth testCam testBox
    ok = (w != undefined) and (abs(w - 400.0) < 0.01)
    detail = "Projected width = " + (w as string)
)
catch
(
    detail = "MAXScript exception in geometry test."
)
try (if isValidNode testCam do delete testCam) catch()
try (if isValidNode testBox do delete testBox) catch()
if ok then messageBox ("PASS\n\n" + detail) title:"AOPR Geometry Test"
else messageBox ("FAIL\n\n" + detail) title:"AOPR Geometry Test"
