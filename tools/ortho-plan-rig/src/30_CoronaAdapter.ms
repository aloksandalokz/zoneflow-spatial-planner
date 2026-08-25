/* AOPR 30_CoronaAdapter.ms */

global AOPR_CORONA_PROJECTION_PROP = undefined
global AOPR_CORONA_ORTHO_VALUE = undefined
global AOPR_CORONA_SIZE_PROP = undefined

fn AOPR_TrySetProjectionCandidate cam propName value =
(
    local oldValue = AOPR_SafeGet cam propName
    local ok = AOPR_SafeSet cam propName value
    if not ok then false
    else
    (
        redrawViews()
        local state = AOPR_ProjectionStateFromViewport cam
        if state == #orthographic then true
        else
        (
            if oldValue != undefined do AOPR_SafeSet cam propName oldValue
            false
        )
    )
)

fn AOPR_DiscoverOrthographicProjection cam =
(
    if not (AOPR_IsValidNode cam) then false
    else
    (
        AOPR_CORONA_PROJECTION_PROP = undefined
        AOPR_CORONA_ORTHO_VALUE = undefined

        if isProperty cam #orthoProjection do
        (
            local old = AOPR_SafeGet cam #orthoProjection
            if AOPR_SafeSet cam #orthoProjection true do
            (
                redrawViews()
                if (AOPR_ProjectionStateFromViewport cam) == #orthographic do
                (
                    AOPR_CORONA_PROJECTION_PROP = #orthoProjection
                    AOPR_CORONA_ORTHO_VALUE = true
                    return true
                )
            )
            if old != undefined do AOPR_SafeSet cam #orthoProjection old
        )

        local props = AOPR_CoronaCandidateProjectionProps cam
        for p in props do
        (
            local cur = AOPR_SafeGet cam p
            if cur != undefined do
            (
                local cls = classOf cur
                if cls == BooleanClass do
                (
                    if AOPR_TrySetProjectionCandidate cam p true do
                    (
                        AOPR_CORONA_PROJECTION_PROP = p
                        AOPR_CORONA_ORTHO_VALUE = true
                        return true
                    )
                )
                if cls == Name do
                (
                    for v in #(#orthographic,#ortho,#orthogonal) do
                        if AOPR_TrySetProjectionCandidate cam p v do
                        (
                            AOPR_CORONA_PROJECTION_PROP = p
                            AOPR_CORONA_ORTHO_VALUE = v
                            return true
                        )
                )
                if cls == String do
                (
                    for v in #("Orthographic","orthographic","Ortho","ortho") do
                        if AOPR_TrySetProjectionCandidate cam p v do
                        (
                            AOPR_CORONA_PROJECTION_PROP = p
                            AOPR_CORONA_ORTHO_VALUE = v
                            return true
                        )
                )
                if cls == Integer do
                (
                    for v = 0 to 12 do
                        if AOPR_TrySetProjectionCandidate cam p v do
                        (
                            AOPR_CORONA_PROJECTION_PROP = p
                            AOPR_CORONA_ORTHO_VALUE = v
                            return true
                        )
                )
            )
        )
        false
    )
)

fn AOPR_DiscoverOrthoSizeProperty cam =
(
    AOPR_CORONA_SIZE_PROP = undefined
    if not (AOPR_IsValidNode cam) then undefined
    else
    (
        local preferred = #(#orthoViewSize,#orthographicViewSize,#orthoSize,#orthographicSize,#ortho_view_size)
        for p in preferred while AOPR_CORONA_SIZE_PROP == undefined do
        (
            if isProperty cam p do
            (
                local v = AOPR_SafeGet cam p
                if (classOf v == Float) or (classOf v == Integer) do AOPR_CORONA_SIZE_PROP = p
            )
        )

        if AOPR_CORONA_SIZE_PROP == undefined do
        (
            for p in (AOPR_CoronaCandidateOrthoSizeProps cam) while AOPR_CORONA_SIZE_PROP == undefined do
            (
                local v = AOPR_SafeGet cam p
                if (classOf v == Float) or (classOf v == Integer) do AOPR_CORONA_SIZE_PROP = p
            )
        )
        AOPR_CORONA_SIZE_PROP
    )
)

fn AOPR_SetCoronaOrthographic cam =
(
    if AOPR_CORONA_PROJECTION_PROP != undefined then
        AOPR_SafeSet cam AOPR_CORONA_PROJECTION_PROP AOPR_CORONA_ORTHO_VALUE
    else
        AOPR_DiscoverOrthographicProjection cam
)

fn AOPR_SetCoronaOrthoWidth cam width =
(
    if width <= 0 then false
    else
    (
        local p = if AOPR_CORONA_SIZE_PROP != undefined then AOPR_CORONA_SIZE_PROP else AOPR_DiscoverOrthoSizeProperty cam
        if p == undefined then false else AOPR_SafeSet cam p width
    )
)
