# host_webrtc.py
import asyncio, json, base64, io, time
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer
from aiortc.contrib.signaling import BYE
import websockets
import mss
from PIL import Image

SIGNAL_SERVER = "ws://localhost:8765"  # reemplazá con IP del server
TOKEN = "Eqdvi2D383/N1UgSHW8C8W9bibSug/rVL1rzEDnitwk6BMcrTRRid+w4XRrzVXjm30NQI88U3r/OX+R95eJQ9g=="  # token generado por tu server previo
ICE_SERVERS = [{"urls": "stun:stun.l.google.com:19302"}]

async def run():
    pc = RTCPeerConnection(configuration=RTCConfiguration([RTCIceServer(**ice) for ice in ICE_SERVERS]))

    # Creamos datachannel
    channel = pc.createDataChannel("frames")

    @channel.on("open")
    def on_open():
        print("DataChannel abierto. Empezando a enviar frames...")

    @channel.on("close")
    def on_close():
        print("DataChannel cerrado.")

    # ICE: cuando hay candidato, deberíamos enviarlo por signaling server,
    # pero aiortc lo emitirá en pc.on("icecandidate"). Lo hacemos abajo.

    # conectar al signaling server
    async with websockets.connect(SIGNAL_SERVER) as sig:
        # anunciar rol
        await sig.send(json.dumps({"role":"host","token":TOKEN}))
        resp = json.loads(await sig.recv())
        print("Signaling ->", resp)

        # crear offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # enviar offer por signaling
        await sig.send(json.dumps({"type":"sdp","sdp":pc.localDescription.sdp,"sdpType":pc.localDescription.type}))

        # escuchar mensajes de signaling en otra tarea
        async def sig_listener():
            async for raw in sig:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                t = data.get("type")
                if t == "sdp":
                    # answer
                    desc = RTCSessionDescription(sdp=data["sdp"], type=data["sdpType"])
                    await pc.setRemoteDescription(desc)
                elif t == "candidate":
                    c = data.get("candidate")
                    if c:
                        cand = RTCIceCandidate(
                            sdpMid=c.get("sdpMid"),
                            sdpMLineIndex=c.get("sdpMLineIndex"),
                            candidate=c.get("candidate")
                        )
                        await pc.addIceCandidate(cand)
                elif t == "bye":
                    print("Remote said BYE")
                    break

        # enviar ICE candidates generados por aiortc al signaling server
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

        # lanzar listener
        listener_task = asyncio.create_task(sig_listener())

        # una vez DataChannel abierto, empezar a enviar frames
        async def send_frames_loop():
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                while True:
                    # esperar hasta que channel esté abierto
                    if channel.readyState != "open":
                        await asyncio.sleep(0.05)
                        continue

                    sct_img = sct.grab(monitor)
                    im = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                    # opcional: resize
                    # im = im.resize((im.width//2, im.height//2))
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=80)
                    jpg = buf.getvalue()
                    try:
                        # enviar binario por datachannel
                        channel.send(jpg)
                    except Exception as e:
                        print("Error enviando frame:", e)
                        return
                    # fps
                    await asyncio.sleep(0.1)  # 10 FPS

        sender_task = asyncio.create_task(send_frames_loop())

        # esperar cierre o tasks
        await listener_task
        sender_task.cancel()
        await pc.close()

if __name__ == "__main__":
    asyncio.run(run())
