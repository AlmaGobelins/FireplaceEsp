import network
import time
import gc
from machine import Pin

try:
    import uselect as select
except ImportError:
    import select

# Import de la classe WebSocketClient (celle avec la reconnexion automatique)
from WebSocketClient import WebSocketClient

# Configuration WiFi
WIFI_SSID = "TP-Link_0C51"
WIFI_PASSWORD = "43489381"
WEBSOCKET_URL = "ws://192.168.0.166:8080/espBougie"

# Configuration de la LED
led = Pin(27, Pin.OUT)

def connect_wifi():
    """
    Connexion Wi-Fi en boucle sans limite de temps,
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

    # 1) Connexion Wi-Fi
    if not connect_wifi():
        print("Impossible de continuer sans connexion WiFi")
        return

    # 2) Instanciation du client WebSocket
    #    ping_interval=20 par exemple (ajustez si besoin).
    ws = WebSocketClient(WEBSOCKET_URL, ping_interval=20)

    # 3) Reconnexion automatique (boucle interne jusqu'à succès).
    #    Cette méthode appelera 'connect()' et, en cas d'échec ou de déconnexion,
    #    réessayera toutes les 5 secondes jusqu'à réussir.
    ws._reconnect()

    # Pour la lecture partielle, on passe le socket en non-bloquant.
    # Note : à chaque reconnexion, le socket est recréé,
    #        donc vous devrez éventuellement reconfigurer ce mode après chaque connect()
    #        si vous avez besoin de conserver le non-bloquant dans tous les cas.
    if ws.socket:
        ws.socket.setblocking(False)

    # Pour envoyer périodiquement un "ping" au serveur, on peut utiliser un timer
    # ou simplement un check dans la boucle principale.
    last_ping_time = time.time()
    ping_interval = 15  # secondes

    try:
        # 4) Boucle principale
        while True:
            current_time = time.time()

            # Envoi d'un "ping" périodique
            if (current_time - last_ping_time) >= ping_interval:
                ws.send("ping")
                last_ping_time = current_time

            # Lecture partielle en non-bloquant
            # On récupère 1 octet si disponible
            try:
                data = ws.socket.recv(1)
                if data:
                    # On repasse en mode bloquant le temps de lire le reste du message
                    ws.socket.setblocking(True)
                    message = ws.receive(first_byte=data)
                    # On repasse en non-bloquant pour les lectures suivantes
                    ws.socket.setblocking(False)

                    if message:
                        print(f"Message reçu : {message}")
                        msg_lower = message.lower()

                        # Réponse automatique aux pings
                        if msg_lower == "ping":
                            ws.send("pong")

                        # Commandes d’allumage
                        if msg_lower == "allumer":
                            led.value(1)

                        if msg_lower == "turn_on_bougie":
                            led.value(1)
                            # Envoi d'un message particulier au serveur ou autre action
                            ws.send("ipadRoberto:play_video_bougie")

            except OSError as e:
                # Erreur EAGAIN => rien de disponible => on ignore
                # Autres erreurs => on relance la connexion
                if e.args and e.args[0] != 11:
                    print("Erreur socket inattendue :", e)
                    # On signale la déconnexion pour forcer la reconnexion
                    ws._on_disconnect()
                    # Après _on_disconnect(), ws._reconnect() est appelé et
                    # un nouveau socket est créé. On peut en profiter pour le repasser
                    # en non-bloquant si nécessaire :
                    if ws.socket:
                        ws.socket.setblocking(False)

            # Petite pause pour réduire la charge CPU
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur.")

    except Exception as e:
        print(f"Erreur inattendue: {e}")

    finally:
        if ws:
            ws.close()
            print("Connexion WebSocket fermée.")

if __name__ == "__main__":
    main()
