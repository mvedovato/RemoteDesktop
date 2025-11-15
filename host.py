# host.py
import asyncio, base64, json, io, time
import mss
from PIL import Image
import websockets

print("WEBSOCKETS VERSION:", websockets.__version__)

TOKEN = "pusIs1PeH49p8UceIStkdcZffyV0ymwgsRxLwbMxD2BQ02UAcE6n5K2Hy1xGKbB48KPmFgmpJURytbbKcMHtDxyFHrT8L03XqiNPp1qNcRnhfqxtyRbe2rQLgwod1lBwsb1Gu6p9LDptOa6E7rNopw=="
SERVER = "ws://localhost:8765"

# ======================================================
#   MANEJO DE MENSAJES DESDE EL SERVER
# ======================================================
async def handle_server_messages(ws):
    """Lee mensajes que el server envía al host."""
    try:
        async for msg in ws:
            if isinstance(msg, bytes):
                # El host no debería recibir binarios
                print("⚠️ Recibido binario no esperado del server")
                continue

            data = json.loads(msg)
            t = data.get("type")

            if t == "control_request":
                print("📩 Viewer pidió control")
                # acá podrías abrir popup, consultar al usuario, etc.
                # por prototipo: aceptar automáticamente
                await ws.send(json.dumps({"type": "grant_control"}))
                print("✔️ Control concedido")

            elif t == "input_event":
                print("📥 Input event recibido desde viewer:", data["event"])

            else:
                print("📡 Mensaje desconocido:", data)

    except websockets.exceptions.ConnectionClosed:
        print("❌ Conexión cerrada por el server")


# ======================================================
#   LOOP DE CAPTURA Y ENVÍO DE FRAMES
# ======================================================
async def send_frames(ws):
    with mss.mss() as sct:
        monitor = sct.monitors[1]

        while True:
            try:
                sct_img = sct.grab(monitor)
                im = Image.frombytes("RGB", sct_img.size, sct_img.rgb)

                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=80)
                jpg = buf.getvalue()

                await ws.send(jpg)

            except websockets.exceptions.ConnectionClosed:
                print("❌ Conexión cerrada durante envío de frame")
                return

            await asyncio.sleep(0.2)   # ~5 FPS


# ======================================================
#   FUNCIÓN PRINCIPAL
# ======================================================
async def run():
    print("Conectando al servidor...")
    async with websockets.connect(SERVER) as ws:

        # Enviar mensaje inicial
        await ws.send(json.dumps({"role": "host", "token": TOKEN}))

        # Esperar respuesta OK del server
        msg = await ws.recv()
        print("server:", msg)

        # Lanzar tareas concurrentes
        consumer = asyncio.create_task(handle_server_messages(ws))
        producer = asyncio.create_task(send_frames(ws))

        await asyncio.wait([consumer, producer], return_when=asyncio.FIRST_COMPLETED)

        print("Host finalizado.")

# ======================================================
if __name__ == "__main__":
    asyncio.run(run())
