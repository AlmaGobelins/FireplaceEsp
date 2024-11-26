import network
import time
from WebSocketClient import WebSocketClient
import gc
from machine import Pin
try:
    import uselect as select
except ImportError:
    import select

# Configuration WiFi
WIFI_SSID = "Bbox-29B0DA0D"
WIFI_PASSWORD = "MRY6fFwVx1KkbMuuqQ"
WEBSOCKET_URL = "ws://192.168.1.99:8080/espFireplaceConnect"  # Remplacez par l'URL de votre serveur

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f'Connexion au réseau {WIFI_SSID}...')
    
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print('Attente de connexion...')
            time.sleep(1)
            
    if wlan.isconnected():
        print('Connexion WiFi réussie!')
        print('Adresse IP:', wlan.ifconfig()[0])
        return True
    else:
        print('Échec de connexion WiFi')
        return False

def main():
    gc.collect()
    
    if not connect_wifi():
        print("Impossible de continuer sans connexion WiFi")
        return
    
    ws = WebSocketClient(WEBSOCKET_URL)
    last_message_time = time.time()
    last_check_time = time.time()
    
    try:
        if ws.connect():
            print("Connecté au serveur WebSocket")
            ws.socket.setblocking(False)
            
            while True:
                current_time = time.time()
                
                # Vérification fréquente des messages (toutes les 100ms)
                if current_time - last_check_time >= 0.1:
                    try:
                        # Tentative de lecture du socket
                        data = ws.socket.recv(1)
                        if data:
                            # Remettre le socket en mode bloquant pour la lecture du message complet
                            ws.socket.setblocking(True)
                            message = ws.receive(first_byte=data)
                            ws.socket.setblocking(False)
                            
                            if message:
                                # Ne pas afficher les échos de nos propres messages
                                if message.lower() == "souffle":
                                    print("================")
                                    print(f"Message reçu: {message}")
                                    print("================")
                                    try:
                                        # Si le message est de la forme "valeur:123.45"
                                        if ":" in message:
                                            value = float(message.split(":")[-1].strip())
                                            print(f"Valeur extraite: {value}")
                                    except ValueError:
                                        pass
                    except OSError as e:
                        if e.args[0] != 11:  # Si ce n'est pas EAGAIN
                            raise
                    last_check_time = current_time
                
                # Envoi périodique (toutes les 5 secondes)
                if current_time - last_message_time >= 5:
                    message = f"{current_time}"
                    if ws.send(message):
                        print(f"Message envoyé: {message}")
                        last_message_time = current_time
                    else:
                        print("Erreur d'envoi du message")
                        raise Exception("Erreur d'envoi")
                
                # Mini délai pour éviter de surcharger le CPU
                time.sleep(0.001)  # 1ms de délai
                
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