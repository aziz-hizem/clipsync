import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QRadioButton, QLineEdit, QPushButton, 
                            QLabel, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import socket
import threading
import time
from typing import Optional
import pyperclip

def get_local_ip():
    """Get the local IP address that other devices can connect to"""
    try:
        # Connect to a remote address to determine the local IP
        # This doesn't actually send data, just determines routing
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception:
        try:
            # Fallback: get hostname IP
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

class ClipSyncWorker(QThread):
    status_update = pyqtSignal(str)
    connection_closed = pyqtSignal()

    def __init__(self, mode: str, host: str, port: int):
        super().__init__()
        self.mode = mode
        self.host = host
        self.port = port
        self.running = True
        self.conn = None

    def send_loop(self, conn: socket.socket):
        last_text: Optional[str] = None
        while self.running:
            try:
                current = pyperclip.paste()
            except Exception:
                current = ""
            if current != last_text and current:
                try:
                    data = current.encode("utf-8")
                    conn.sendall(len(data).to_bytes(4, "big") + data)
                    last_text = current
                except (BrokenPipeError, OSError):
                    break
            time.sleep(0.25)

    def recv_loop(self, conn: socket.socket):
        while self.running:
            try:
                header = conn.recv(4)
                if not header:
                    break
                length = int.from_bytes(header, "big")
                data = b""
                while len(data) < length:
                    chunk = conn.recv(min(64 * 1024, length - len(data)))
                    if not chunk:
                        break
                    data += chunk
                text = data.decode("utf-8")
                if text and pyperclip.paste() != text:
                    pyperclip.copy(text)
            except (BrokenPipeError, OSError):
                break

    def run(self):
        try:
            if self.mode == "server":
                self.run_server()
            else:
                self.run_client()
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
        finally:
            self.connection_closed.emit()

    def run_server(self):
        self.status_update.emit(f"Waiting for connection on {self.host}:{self.port}...")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen(1)
            s.settimeout(1.0)  # Allow checking self.running
            
            while self.running:
                try:
                    self.conn, addr = s.accept()
                    self.status_update.emit(f"Connected to {addr[0]}:{addr[1]}")
                    with self.conn:
                        threading.Thread(target=self.send_loop, args=(self.conn,), daemon=True).start()
                        self.recv_loop(self.conn)
                        if self.running:
                            self.status_update.emit("Connection closed by peer")
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.status_update.emit(f"Error: {str(e)}")
                    break

    def run_client(self):
        self.status_update.emit(f"Connecting to {self.host}:{self.port}...")
        try:
            self.conn = socket.create_connection((self.host, self.port))
            self.status_update.emit("Connected! Clipboard is now shared.")
            with self.conn:
                threading.Thread(target=self.send_loop, args=(self.conn,), daemon=True).start()
                self.recv_loop(self.conn)
                if self.running:
                    self.status_update.emit("Connection closed by peer")
        except Exception as e:
            if self.running:
                self.status_update.emit(f"Error: {str(e)}")

    def stop(self):
        self.running = False
        if self.conn:
            try:
                self.conn.close()
            except:
                pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClipSync")
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Mode selection
        mode_group = QButtonGroup(self)
        mode_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.client_radio = QRadioButton("Client")
        self.server_radio.setChecked(True)
        mode_group.addButton(self.server_radio)
        mode_group.addButton(self.client_radio)
        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        layout.addLayout(mode_layout)

        # IP and Port inputs
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("IP Address:"))
        self.ip_input = QLineEdit()
        self.ip_input.setText("0.0.0.0")
        ip_layout.addWidget(self.ip_input)
        layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit()
        self.port_input.setText("8765")
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)

        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # IP address display (bottom right)
        ip_display_layout = QHBoxLayout()
        ip_display_layout.addStretch()  # Push to the right
        self.ip_display_label = QLabel()
        self.update_ip_display()
        ip_display_layout.addWidget(self.ip_display_label)
        layout.addLayout(ip_display_layout)

        # Window size
        self.setMinimumWidth(300)
        self.setMinimumHeight(220)

        # Connect signals
        self.server_radio.toggled.connect(self.on_mode_changed)
        
    def update_ip_display(self):
        """Update the IP address display"""
        local_ip = get_local_ip()
        self.ip_display_label.setText(f"Your IP address: {local_ip}")
        # Style the label to be smaller and right-aligned
        self.ip_display_label.setStyleSheet("color: gray; font-size: 10px;")
        self.ip_display_label.setAlignment(Qt.AlignmentFlag.AlignRight)
    
    def on_mode_changed(self):
        if self.server_radio.isChecked():
            self.ip_input.setText("0.0.0.0")
            self.ip_display_label.show()
            self.update_ip_display()
        else:
            if self.ip_input.text() == "0.0.0.0":
                self.ip_input.setText("127.0.0.1")
            self.ip_display_label.hide()

    def toggle_connection(self):
        if self.worker is None:
            try:
                port = int(self.port_input.text())
                if not (0 <= port <= 65535):
                    raise ValueError("Port must be between 0 and 65535")
                
                mode = "server" if self.server_radio.isChecked() else "client"
                self.worker = ClipSyncWorker(mode, self.ip_input.text(), port)
                self.worker.status_update.connect(self.update_status)
                self.worker.connection_closed.connect(self.on_connection_closed)
                self.worker.start()
                
                self.connect_button.setText("Disconnect")
                self.server_radio.setEnabled(False)
                self.client_radio.setEnabled(False)
                self.ip_input.setEnabled(False)
                self.port_input.setEnabled(False)
            except ValueError as e:
                QMessageBox.critical(self, "Error", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start: {str(e)}")
                self.worker = None
        else:
            self.disconnect_worker()

    def disconnect_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
            self.connect_button.setText("Connect")
            self.server_radio.setEnabled(True)
            self.client_radio.setEnabled(True)
            self.ip_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.status_label.setText("Ready")

    def update_status(self, message):
        self.status_label.setText(message)

    def on_connection_closed(self):
        self.disconnect_worker()

    def closeEvent(self, event):
        self.disconnect_worker()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()