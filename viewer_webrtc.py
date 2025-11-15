# viewer_webrtc.py
import asyncio, json, cv2, numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import websockets

SIGNAL_SERVER = "ws://<SIGNAL_SERVER_IP>:8765"  # reemplazar
TOKEN = "<PEGA_AQUI_EL_TOKEN>"
ICE_SERVERS = [{"urls": "stun:stun.l.google.com:19302"}]

async def run():
    pc = RTCPeerConnection(configuration=RTCConfiguration([RTCIceServer(**ice) for ice in ICE_SERVERS]))
    frame_queue = asyncio.Queue()

    # data channel handler: se crea cuando la otra parte lo crea (host crea)
    @pc.on("datachannel")
    def on_datachannel(channel):
        print("DataChannel recibido:", channel.label)

        @channel.on("message")
        def on_message(message):
            # mensaje binario -> frame JPEG
            if isinstance(message, (bytes, bytearray)):
                frame_queue.put_nowait(message)

    async with websockets.connect(SIGNAL_SERVER) as sig:
        # anunciar rol
        await sig.send(json.dumps({"role":"viewer","token":TOKEN}))
        resp = json.loads(await sig.recv())
        print("Signaling ->", resp)

        # esperar offer desde host (signaling server relayará el offer)
        # alternativamente, viewer podría pedir directly, pero en nuestro flujo
        # el host crea y envía el offer por signaling y el server lo reenvía aquí.
        # Esperamos messages: we'll loop until we get a "sdp" offer
        async def sig_listener():
            async for raw in sig:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                t = data.get("type")
                if t == "sdp":
                    # offer from host
                    desc = RTCSessionDescription(sdp=data["sdp"], type=data["sdpType"])
                    await pc.setRemoteDescription(desc)
                    # create answer
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    # send answer
                    await sig.send(json.dumps({"type":"sdp","sdp":pc.localDescription.sdp,"sdpType":pc.localDescription.type}))
                elif t == "candidate":
                    c = data.get("candidate")
                    if c:
                        from aiortc import RTCIceCandidate
                        cand = RTCIceCandidate(sdpMid=c.get("sdpMid"), sdpMLineIndex=c.get("sdpMLineIndex"), candidate=c.get("candidate"))
                        await pc.addIceCandidate(cand)
                elif t == "bye":
                    break

        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await sig.send(json.dumps({
                    "type":"candidate",
                    "candidate": {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex
                    }
                }))

        listener = asyncio.create_task(sig_listener())

        # frame display loop
        async def display_loop():
            cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
            while True:
                jpg = await frame_queue.get()
                arr = np.frombuffer(jpg, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    cv2.imshow("Remote Desktop", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            cv2.destroyAllWindows()

        disp_task = asyncio.create_task(display_loop())

        await asyncio.wait([listener, disp_task], return_when=asyncio.FIRST_COMPLETED)
        listener.cancel()
        disp_task.cancel()
        await pc.close()

if __name__ == "__main__":
    asyncio.run(run())
