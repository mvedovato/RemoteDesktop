# viewer.py
import asyncio
import json
import cv2
import numpy as np
import websockets

TOKEN = "H5h1MTkaDKinX+iOH+8ahf8m05sKtw07KLQuZGQLvN/wR2ivXCSKjLvNwgU2UepmakUgv/K1Z9g9MRiqNZbabAkWX6feedkyqRRe6qQGihl9NXvZlM/AHPUSQHoCon7V4EJ9GI/4OmmELKfOYqxtTw=="
SERVER = "ws://localhost:8765"   # usar wss en prod


async def run():
    print("Conectando al server...")
    async with websockets.connect(SERVER) as ws:

        # Login inicial
        await ws.send(json.dumps({"role": "viewer", "token": TOKEN}))

        # Esperamos OK del server
        resp = await ws.recv()
        print("server:", resp)

        print("📡 Conectado. Esperando frames...")
        cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)

        # único lector del websocket
        while True:
            msg = await ws.recv()

            if isinstance(msg, bytes):
                # Frame JPEG
                arr = np.frombuffer(msg, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                if img is not None:
                    cv2.imshow("Remote Desktop", img)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Cerrando visor...")
                    break

            else:
                # JSON de control
                data = json.loads(msg)
                print("[JSON]", data)

        cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(run())
