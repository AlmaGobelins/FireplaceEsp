import network
import time
import gc
from machine import Pin
try:
    import uselect as select
except ImportError:
    import select

# Import de la classe WebSocketClient (version adaptée pour ignorer EAGAIN)
from WebSocketClient import WebSocketClient

# Configuration WiFi
WIFI_SSID = "TP-Link_0C51"
WIFI_PASSWORD = "43489381"
WEBSOCKET_URL = "ws://192.168.0.166:8080/espBougie"

# Configuration de la LED
led = Pin(27, Pin.OUT)

def connect_wifi():
    """
    Tentative de connexion Wi-Fi en boucle,
    sans limite stricte de temps, 
    pour éviter de quitter si le réseau est lent.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"Connexion au réseau {WIFI_SSID}...")

    if wlan.isconnected():
        print("Déjà connecté au Wi-Fi.")
        print("Adresse IP:", wlan.ifconfig()[0])
        return True

    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        print("Attente de connexion...")
        time.sleep(1)

    print("Connexion WiFi réussie!")
    print("Adresse IP:", wlan.ifconfig()[0])
    return True

def main():
    gc.collect()

    # 1) Connexion Wi-Fi en boucle
    if not connect_wifi():
        print("Impossible de continuer sans connexion WiFi")
        return

    # 2) Instanciation du WebSocketClient
    ws = WebSocketClient(WEBSOCKET_URL)
    last_check_time = time.time()

    try:
        # 3) Première connexion au WebSocket
        if ws.connect():
            print("Connecté au serveur WebSocket")
            # Socket en non-bloquant pour pouvoir faire recv(1)
            ws.socket.setblocking(False)
        else:
            print("Échec de connexion au WebSocket.")
            # Selon ta classe, si tu veux une reconnexion automatique,
            # appelle ws._reconnect() ici:
            # ws._reconnect()

        # 4) Boucle principale
        while True:
            current_time = time.time()

            # Vérification fréquente des messages (toutes les 100 ms)
            if (current_time - last_check_time) >= 0.1:
                try:
                    # Lecture d'un octet en non-bloquant
                    data = ws.socket.recv(1)
                    if data:
                        # Repasser en bloquant pour lire tout le message
                        ws.socket.setblocking(True)
                        message = ws.receive(first_byte=data)
                        ws.socket.setblocking(False)

                        if message:
                            # Répondre au ping du serveur
                            
                            if message.lower() == "ping":
                                ws.send("pong")

                            # Commandes reconnues
                            if message.lower() == "allumer":
                                print(message.lower())
                                led.value(1)

                            if message.lower() == "turn_on_bougie":
                                print(message.lower())
                                led.value(1)
                                ws.send("ipadRoberto:play_video_bougie")

                except OSError as e:
                    # e.args[0] == 11 => EAGAIN => on ignore
                    # toute autre erreur => on la relance ou on force une reconnexion
                    if e.args and e.args[0] != 11:
                        print("Erreur socket inattendue :", e)
                        # Ici, tu peux décider de relancer la connexion :
                        # ws._on_disconnect() ou ws._reconnect()
                        # Ou simplement raise pour planter et voir l'erreur
                        raise

                last_check_time = current_time

            # Mini pause pour éviter la surcharge CPU
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur")

    except Exception as e:
        print(f"Erreur: {e}")

    finally:
        if ws:
            ws.close()
            print("Connexion WebSocket fermée")

if __name__ == "__main__":
    main()
