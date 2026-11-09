from gradio_client import Client

SPACE = "KlingTeam/LivePortrait"
PHOTO = r"C:\AI_UGC_STUDIO\LivePortrait\assets\examples\source\s0.jpg"
DRIVING = r"C:\AI_UGC_STUDIO\projects\driving_short15.mp4"

client = Client(SPACE)
res = client.predict(PHOTO, {"video": DRIVING, "subtitles": None}, True, True, True,
                       api_name="/gpu_wrapped_execute_video")
print("RESP_TYPE", type(res))
print("RESP", str(res)[:500])
