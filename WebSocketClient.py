import usocket as socket
import ubinascii
import uhashlib
import urandom as random

class WebSocketClient:
    def __init__(self, url, ping_interval=20):
        self.url = url
        self.socket = None
        self.connected = False
        self.ping_interval = ping_interval
        self._parse_url()
        
    def _parse_url(self):
        proto, dummy, host, path = self.url.split('/', 3)
        if ':' in host:
            self.host, port = host.split(':')
            self.port = int(port)
        else:
            self.host = host
            self.port = 80
        self.path = '/' + path
        
    def _generate_key(self):
        rand = bytes([random.getrandbits(8) for _ in range(16)])
        return ubinascii.b2a_base64(rand)[:-1]

    def _apply_mask(self, data, mask):
        masked = bytearray(len(data))
        for i in range(len(data)):
            masked[i] = data[i] ^ mask[i % 4]
        return masked

    def _read_exactly(self, num_bytes):
        data = bytearray()
        while len(data) < num_bytes:
            try:
                chunk = self.socket.recv(1)
                if not chunk:
                    return None
                data.extend(chunk)
            except:
                return None
        return data
        
    def connect(self):
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
                '',
                ''
            ]
            
            self.socket.send('\r\n'.join(headers).encode())
            
            response = self.socket.recv(4096).decode()
            
            if "101 Switching Protocols" in response:
                self.connected = True
                return True
            else:
                return False
                
        except Exception as e:
            print("Erreur de connexion:", e)
            return False

    def receive(self, first_byte=None):
        try:
            print("Début de receive()")
            # Premier byte
            if first_byte:
                fin = first_byte[0] & 0x80
                opcode = first_byte[0] & 0x0F
                print(f"Premier byte reçu: fin={fin}, opcode={opcode}")
            else:
                first = self._read_exactly(1)
                if not first:
                    return None
                fin = first[0] & 0x80
                opcode = first[0] & 0x0F
                print(f"Premier byte lu: fin={fin}, opcode={opcode}")

            # Deuxième byte
            second = self._read_exactly(1)
            if not second:
                print("Pas de second byte")
                return None
            print("Second byte reçu")
                
            mask = second[0] & 0x80
            payload_length = second[0] & 0x7F
            print(f"Mask: {mask}, Payload length: {payload_length}")

            # Gestion des longueurs étendues
            if payload_length == 126:
                length_data = self._read_exactly(2)
                if not length_data:
                    print("Erreur lecture longueur 126")
                    return None
                payload_length = int.from_bytes(length_data, 'big')
            elif payload_length == 127:
                length_data = self._read_exactly(8)
                if not length_data:
                    print("Erreur lecture longueur 127")
                    return None
                payload_length = int.from_bytes(length_data, 'big')
            
            print(f"Longueur finale du payload: {payload_length}")

            # Lecture du masque si présent
            mask_bits = None
            if mask:
                mask_bits = self._read_exactly(4)
                if not mask_bits:
                    print("Erreur lecture masque")
                    return None
                print("Masque lu")

            # Lecture du payload
            print(f"Lecture de {payload_length} octets de payload")
            payload = self._read_exactly(payload_length)
            if not payload:
                print("Erreur lecture payload")
                return None
            print(f"Payload lu: {len(payload)} octets")

            # Démasquage si nécessaire
            if mask_bits:
                payload = self._apply_mask(payload, mask_bits)
                print("Payload démasqué")

            # Traitement selon l'opcode
            if opcode == 0x1:  # Text
                try:
                    message = payload.decode('utf-8')
                    print(f"Message décodé: {message}")
                    return message
                except UnicodeError:
                    print("Erreur décodage UTF-8")
                    return None
            elif opcode == 0x9:  # Ping
                print("Ping reçu")
                self.send_pong()
                return None
            elif opcode == 0x8:  # Close
                print("Trame de fermeture reçue")
                self.close()
                return None
            else:
                print(f"Opcode non géré: {opcode}")
                return None

        except Exception as e:
            print(f"Erreur dans receive: {e}")
            return None

    def send(self, data):
        if not self.connected:
            raise Exception("Non connecté au serveur")
            
        data_bytes = data.encode()
        mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
        header = bytearray()
        
        header.append(0b10000001)  # FIN + Opcode TEXT
        
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
            return False

    def send_pong(self):
        if self.connected:
            try:
                mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
                header = bytearray([0x8A, 0x80])
                header.extend(mask_bytes)
                self.socket.send(header)
            except:
                pass
            
    def close(self):
        if self.connected:
            try:
                mask_bytes = bytes([random.getrandbits(8) for _ in range(4)])
                header = bytearray([0x88, 0x80])
                header.extend(mask_bytes)
                self.socket.send(header)
                self.socket.close()
            except:
                pass
        self.connected = False