/* AOPR 00_Core.ms */

global AOPR_VERSION = "4.0-codex"
global AOPR_GREEN = color 0 255 0
global AOPR_TAG = "AOPR_RIG"
global AOPR_VIEW_TAG = "AOPR_VIEW"

global AOPR_LOG_LINES = #()

fn AOPR_Log_Reset =
(
    AOPR_LOG_LINES = #()
)

fn AOPR_Log msg =
(
    local s = msg as string
    append AOPR_LOG_LINES s
    format "%\n" s
    s
)

fn AOPR_IsValidNode n =
(
    (n != undefined) and (isValidNode n)
)

fn AOPR_SafeGet obj propName =
(
    local out = undefined
    if obj != undefined do
    (
        try
        (
            if isProperty obj propName do out = getProperty obj propName
        )
        catch()
    )
    out
)

fn AOPR_SafeSet obj propName value =
(
    local ok = false
    if obj != undefined do
    (
        try
        (
            if isProperty obj propName do
            (
                setProperty obj propName value
                ok = true
            )
        )
        catch()
    )
    ok
)

fn AOPR_TagNode n viewName:"" =
(
    if AOPR_IsValidNode n do
    (
        try (setUserProp n AOPR_TAG "1") catch()
        if viewName != "" do try (setUserProp n AOPR_VIEW_TAG viewName) catch()
    )
)

fn AOPR_IsRigNode n =
(
    if not (AOPR_IsValidNode n) then false
    else
    (
        local v = ""
        try (v = getUserProp n AOPR_TAG) catch()
        v == "1"
    )
)

fn AOPR_WriteLog path =
(
    local f = createFile path
    if f == undefined then false
    else
    (
        for line in AOPR_LOG_LINES do format "%\n" line to:f
        close f
        true
    )
)
