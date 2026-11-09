from gradio_client import Client

for space in ("innoai/LivePortrait", "KlingTeam/LivePortrait"):
    try:
        c = Client(space)
        api = c.view_api()
        print("SPACE", space, "API_OK", type(api))
        if isinstance(api, dict):
            eps = list((api.get("named_endpoints") or {}).keys())
            print("  ENDPOINTS", eps)
        if space.endswith("LivePortrait"):
            q = {"video": r"C:\AI_UGC_STUDIO\projects\driving_short15.mp4", "subtitles": None}
            res = c.predict(r"C:\AI_UGC_STUDIO\LivePortrait\assets\examples\source\s0.jpg", q, True, True, True,
                            api_name="/gpu_wrapped_execute_video")
            print("  PRED_OK", str(res)[:250])
    except Exception as exc:
        print("  FAIL", space, str(exc)[:220])
