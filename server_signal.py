# server_signal.py
import asyncio, json, time, secrets, base64
import websockets

SESSIONS = {}  # token -> {"host": ws, "viewer": ws, "queue": []}

def generate_token():
    raw = secrets.token_bytes(64)
    return base64.b64encode(raw).decode()

TEMP_TOKEN = generate_token()
print("⚠️  WARNING: Generando TOKEN temporal (solo dev)")
print("Token ejemplo:", TEMP_TOKEN)
print()

async def send_or_queue(session, target_key, message):
    """Si peer está conectado lo enviamos, si no lo encolamos."""
    peer = session.get(target_key)
    if peer:
        try:
            await peer.send(message)
            return True
        except Exception as e:
            print(f"[{time.strftime('%X')}] Error enviando a {target_key}: {e}")
            # si falla el envío, encolamos
    # encolar
    session.setdefault("queue", []).append((target_key, message))
    return False

async def flush_queue_for(session, target_key):
    """Enviar todos los mensajes encolados dirigidos a target_key."""
    q = session.get("queue")
    if not q:
        return
    remaining = []
    for tk, msg in q:
        if tk == target_key:
            peer = session.get(target_key)
            if peer:
                try:
                    await peer.send(msg)
                    # enviado
                    continue
                except Exception as e:
                    print(f"[{time.strftime('%X')}] Error reenviando queued msg to {target_key}: {e}")
                    remaining.append((tk, msg))
            else:
                remaining.append((tk, msg))
        else:
            remaining.append((tk, msg))
    session["queue"] = remaining

async def handler(ws):
    token = None
    role = None
    try:
        # primer mensaje: {"role":"host"|"viewer","token":"..."}
        msg = await ws.recv()
        obj = json.loads(msg)
        role = obj.get("role")
        token = obj.get("token")
        if not role or not token:
            await ws.send(json.dumps({"type":"error","msg":"missing role/token"}))
            await ws.close()
            return

        if token not in SESSIONS:
            SESSIONS[token] = {"host": None, "viewer": None, "queue": []}

        session = SESSIONS[token]
        if role == "host":
            session["host"] = ws
            print(f"[{time.strftime('%X')}] Host connected for token {token[:8]}")
            await ws.send(json.dumps({"type":"ok","role":"host"}))
            # si hay mensajes pendientes para viewer, cuando viewer llegue se reenviarán.
            # también intentar vaciar cola dirigida al host (por si viewer se conectó antes y encoló)
            await flush_queue_for(session, "host")

        elif role == "viewer":
            session["viewer"] = ws
            print(f"[{time.strftime('%X')}] Viewer connected for token {token[:8]}")
            await ws.send(json.dumps({"type":"ok","role":"viewer"}))
            # al conectar viewer, reenviamos todo lo que estaba encolado para viewer
            await flush_queue_for(session, "viewer")
        else:
            await ws.send(json.dumps({"type":"error","msg":"invalid role"}))
            await ws.close()
            return

        # relaying signaling messages
        async for raw in ws:
            # esperamos mensajes JSON
            try:
                data = json.loads(raw)
            except Exception:
                # ignorar payloads no JSON de signaling
                continue

            # definimos a quién va dirigido:
            if role == "host":
                target = "viewer"
            else:
                target = "host"

            # si peer conectado, intentar enviar; si no, encolar
            peer = session.get(target)
            if peer:
                try:
                    await peer.send(json.dumps(data))
                except Exception as e:
                    print(f"[{time.strftime('%X')}] Error reenvio directo: {e} -> encolando")
                    session.setdefault("queue", []).append((target, json.dumps(data)))
            else:
                # peer no conectado: encolamos
                session.setdefault("queue", []).append((target, json.dumps(data)))
                # opcional: avisar al emisor que se encoló
                await ws.send(json.dumps({"type":"info","msg":"peer-not-connected; message queued"}))

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        # cleanup
        if token and token in SESSIONS:
            s = SESSIONS[token]
            if s.get("host") is ws:
                s["host"] = None
                print(f"[{time.strftime('%X')}] Host disconnected for token {token[:8]}")
            if s.get("viewer") is ws:
                s["viewer"] = None
                print(f"[{time.strftime('%X')}] Viewer disconnected for token {token[:8]}")
            if s.get("host") is None and s.get("viewer") is None:
                del SESSIONS[token]

async def main():
    print("Signaling server listening on :8765")
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
