/* AOPR 99_UI.ms */

global AOPR_UI
try (destroyDialog AOPR_UI) catch()

rollout AOPR_UI "Alok Ortho Plan Rig v4" width:420
(
    local gridFront = undefined
    local gridBack = undefined
    local gridLeft = undefined
    local gridRight = undefined
    local gridTop = undefined

    label lblInfo "Corona orthographic plan cameras - diagnostic-first build" align:#left
    button btnProbe "1. RUN CORONA PROBE" width:390 height:32
    button btnTests "2. RUN MODULE TESTS" width:390 height:32
    label lblStatus "Status: not tested" align:#left

    groupBox gbViews "Camera rigs" pos:[10,115] width:400 height:255

    pickbutton pbFront "Pick FRONT grid" pos:[25,145] width:150 autoDisplay:true
    button btFront "Create / Fit FRONT" pos:[190,145] width:190

    pickbutton pbBack "Pick BACK grid" pos:[25,185] width:150 autoDisplay:true
    button btBack "Create / Fit BACK" pos:[190,185] width:190

    pickbutton pbLeft "Pick LEFT grid" pos:[25,225] width:150 autoDisplay:true
    button btLeft "Create / Fit LEFT" pos:[190,225] width:190

    pickbutton pbRight "Pick RIGHT grid" pos:[25,265] width:150 autoDisplay:true
    button btRight "Create / Fit RIGHT" pos:[190,265] width:190

    pickbutton pbTop "Pick TOP grid" pos:[25,305] width:150 autoDisplay:true
    button btTop "Create / Fit TOP" pos:[190,305] width:190

    button btDup "MAKE 4 TOP CLIP DUPLICATES" pos:[25,335] width:355 height:25

    fn showResult r =
    (
        if r[1] then lblStatus.text = "Status: PASS - " + r[2]
        else lblStatus.text = "Status: FAIL - " + r[2]
    )

    on btnProbe pressed do
    (
        local path = (getDir #userScripts) + "\\AOPR_CoronaProbe.txt"
        local ok = AOPR_DumpCoronaProbe path
        lblStatus.text = if ok then ("Status: probe saved: " + path) else ("Status: probe failed; log: " + path)
        messageBox lblStatus.text title:"AOPR Corona Probe"
    )

    on btnTests pressed do
    (
        AOPR_RunAllTests()
        local path = (getDir #userScripts) + "\\AOPR_TestLog.txt"
        AOPR_WriteLog path
        lblStatus.text = "Status: tests finished - see Listener + test log"
        messageBox ("Tests finished.\n\n" + path) title:"AOPR Tests"
    )

    on pbFront picked obj do gridFront = obj
    on pbBack picked obj do gridBack = obj
    on pbLeft picked obj do gridLeft = obj
    on pbRight picked obj do gridRight = obj
    on pbTop picked obj do gridTop = obj

    on btFront pressed do showResult (AOPR_BuildOrFit "ORTHO_FRONT" gridFront #front)
    on btBack pressed do showResult (AOPR_BuildOrFit "ORTHO_BACK" gridBack #back)
    on btLeft pressed do showResult (AOPR_BuildOrFit "ORTHO_LEFT" gridLeft #left)
    on btRight pressed do showResult (AOPR_BuildOrFit "ORTHO_RIGHT" gridRight #right)
    on btTop pressed do showResult (AOPR_BuildOrFit "ORTHO_TOP" gridTop #top)

    on btDup pressed do
    (
        local topCam = getNodeByName "ORTHO_TOP" exact:true
        showResult (AOPR_MakeTopDuplicates topCam)
    )
)

createDialog AOPR_UI style:#(#style_titlebar,#style_sysmenu,#style_toolwindow)
