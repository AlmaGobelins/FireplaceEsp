import usocket as socket
import ubinascii
import uhashlib
import urandom as random
import time

class WebSocketClient:
    def __init__(self, url, ping_interval=20):
        self.url = url
        self.socket = None
        self.connected = False
        self.ping_interval = ping_interval
        self._parse_url()

    def _parse_url(self):
        """
        Analyse l'URL pour en extraire l'hôte, le port, et le chemin.
        Exemples d'URL :
          - ws://192.168.1.10:8080/path
          - ws://serveur.com/ws
        """
        proto, dummy, host, path = self.url.split('/', 3)
        if ':' in host:
            self.host, port = host.split(':')
            self.port = int(port)
        else:
            self.host = host
            self.port = 80
        self.path = '/' + path

    def _generate_key(self):
        """
        Génère une clé aléatoire pour l'en-tête Sec-WebSocket-Key.
        """
        rand = bytes([random.getrandbits(8) for _ in range(16)])
        return ubinascii.b2a_base64(rand)[:-1]

    def _apply_mask(self, data, mask):
        """
        Applique le masque (XOR) aux données (RFC 6455).
        """
        masked = bytearray(len(data))
        for i in range(len(data)):
            masked[i] = data[i] ^ mask[i % 4]
        return masked

    def connect(self):
        """
        Établit la connexion WebSocket avec le serveur.
        Retourne True si la connexion a réussi, False sinon.
        (Pas de boucle de reconnexion ici : on effectue juste une tentative.)
        """
        try:
            self.socket = socket.socket()
            self.socket.connect((self.host, self.port))

            key = self._generate_key()
            headers = [
                'GET {} HTTP/1.1'.format(self.path),
                'Host: {}:{}'.format(self.host, self.port),
                'Connection: Upgrade',
                'Upgrade: websocket',
                'Sec-WebSocket-Key: {}'.format(key.decode()),
                'Sec-WebSocket-Version: 13',
                'Origin: http://{}:{}'.format(self.host, self.port),
                '',  # Ligne vide
                ''
            ]

            # Envoi de la requête HTTP d'upgrade
            self.socket.send('\r\n'.join(headers).encode())

            response = self.socket.recv(4096).decode()
            if "101 Switching Protocols" in response:
                self.connected = True
                print("Connexion WebSocket établie.")
                return True
            else:
                print("Réponse inattendue du serveur:\n", response)
                self.close()
                return False

        except Exception as e:
            print("Erreur de connexion:", e)
            self.close()
            return False

    def _on_disconnect(self):
        """
        Méthode appelée lorsqu'une déconnexion ou une erreur
        de lecture/écriture est détectée. 
        """
        if self.connected:
            print("Déconnexion détectée. Tentative de reconnexion...")
        self.connected = False
        self._reconnect()

    def _reconnect(self):
        """
        Boucle de reconnexion bloquante :
        tente de se reconnecter jusqu'à réussir.
        """
        self.close()  # S'assurer que tout est fermé
        while not self.connected:
            print("Tentative de reconnexion au WebSocket...")
            if self.connect():
                print("Réconnexion réussie.")
            else:
                print("Nouvel essai dans 5 secondes...")
                time.sleep(5)

    def _read_exactly(self, num_bytes):
        data = bytearray()
        remaining = num_bytes
        while remaining > 0:
            try:
                chunk_size = min(1024, remaining)
                chunk = self.socket.recv(chunk_size)
                if not chunk:
                    # Si le serveur a fermé la connexion
                    self._on_disconnect()
                    return None
                data.extend(chunk)
                remaining -= len(chunk)
            except OSError as e:
                # EAGAIN => on n'a juste pas de data pour l'instant
                if e.args and e.args[0] == 11:  # EAGAIN
                    # On peut décider de:
                    # - retourner None (signifiant "pas de data dispo")
                    # - ou lever une exception custom 
                    return None
                else:
                    print(f"Erreur de lecture: {e}")
                    self._on_disconnect()
                    return None
            except Exception as e:
                print(f"Erreur de lecture: {e}")
                self._on_disconnect()
                return None
        return data


    def receive(self, first_byte=None):
        try:
            # Lecture du premier octet
            if first_byte:
                fin = first_byte[0] & 0x80
                opcode = first_byte[0] & 0x0F
            else:
                first = self._read_exactly(1)
                if not first:
                    return None
                fin = first[0] & 0x80
                opcode = first[0] & 0x0F

            # Lecture du deuxième octet
            second = self._read_exactly(1)
            if not second:
                return None
            mask = second[0] & 0x80
            payload_length = second[0] & 0x7F

            # Gestion des longueurs étendues
            if payload_length == 126:
                length_data = self._read_exactly(2)
                if not length_data:
                    return None
                payload_length = int.from_bytes(length_data, 'big')
            elif payload_length == 127:
                length_data = self._read_exactly(8)
                if not length_data:
                    return None
                payload_length = int.from_bytes(length_data, 'big')

            # Lecture du masque si présent
            mask_bits = None
            if mask:
                mask_bits = self._read_exactly(4)
                if not mask_bits:
                    return None

            # Lecture du payload
            if payload_length > 0:
                payload = self._read_exactly(payload_length)
                if not payload:
                    return None
                if mask_bits:
                    payload = self._apply_mask(payload, mask_bits)
            else:
                payload = b''

            # Gestion des opcodes
            if opcode == 0x8:  # Close
                print("Trame de fermeture reçue (opcode=0x8).")
                self.close()
                self._reconnect()
                return None

            elif opcode == 0x1:  # Text
                try:
                    message = payload.decode('utf-8')
                    return message
                except UnicodeError:
                    print("Erreur de décodage UTF-8.")
                    return None

            elif opcode == 0x9:  # Ping
                self.send_pong()
                return None

            else:
                # Autres opcodes (binaire, etc.) non gérés
                return None

        except OSError as e:
            if e.args and e.args[0] == 11:
                # EAGAIN => pas de data => pas de déconnexion
                return None
            else:
                print(f"Erreur dans receive (OSError): {e}")
                self._on_disconnect()
                return None
        except Exception as e:
            print(f"Erreur dans receive: {e}")
            self._on_disconnect()
            return None

    def send(self, data):
        """
        Envoie un message texte au serveur.
        S'il y a une erreur, on tente de se reconnecter automatiquement.
        """
        if not self.connected:
            # Si pas connecté, on tente de se reconnecter
            self._reconnect()

        data_bytes = data.encode()
        mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
        header = bytearray()

        # FIN + opcode texte (0x1)
        header.append(0b10000001)

        length = len(data_bytes)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(length.to_bytes(2, 'big'))
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, 'big'))

        header.extend(mask_bytes)
        masked_data = self._apply_mask(data_bytes, mask_bytes)

        try:
            self.socket.send(header + masked_data)
            return True
        except Exception as e:
            print("Erreur d'envoi:", e)
            self._on_disconnect()
            return False

    def send_pong(self):
        """
        Répond à un ping (opcode=0x9) par un pong (opcode=0xA).
        """
        if self.connected:
            try:
                mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
                header = bytearray([0x8A, 0x80])  # 0xA = Pong
                header.extend(mask_bytes)
                self.socket.send(header)
            except Exception as e:
                print("Erreur lors de l'envoi du Pong:", e)
                self._on_disconnect()

    def close(self):
        """
        Envoie une trame de fermeture (si possible) et ferme le socket.
        """
        if self.connected:
            try:
                mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
                header = bytearray([0x88, 0x80])  # 0x8 = Close
                header.extend(mask_bytes)
                self.socket.send(header)
            except:
                pass
            try:
                self.socket.close()
            except:
                pass

        self.connected = False

