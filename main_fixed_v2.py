import os
import sys
import shutil
import ctypes
from PIL import Image, ImageOps
from functools import partial
from io import BytesIO

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QLineEdit, QProgressBar, QGroupBox,
    QTextEdit, QFileDialog, QSpinBox, QSlider, QFrame, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QMimeData, QThread, Signal, QObject
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QColor, QPalette, QIcon
from PySide6.QtWidgets import QStyle

# === Styling Constants ===
ACTIVE_COLOR = "#3A3A5A"
HOVER_COLOR = "white"
DEFAULT_COLOR = "transparent"
TEXT_COLOR = "#ffd465"
ACTIVE_TEXT_COLOR = "white"
FONT_SIZE = "14px"

BUTTON_STYLE = """
    QPushButton {
        background-color: #3A3A5A;
        color: white;
        border-radius: 10px;
        font-size: 14px;
        padding: 10px 15px;
        min-width: 100px;
    }
    QPushButton:hover {
        background-color: #555;
    }
    QPushButton:pressed {
        background-color: #333;
    }
"""

DRAG_DROP_STYLE = """
    QFrame {
        border: 2px dashed rgba(170, 170, 170, 0.5);
        border-radius: 10px;
        background-color: rgba(249, 249, 249, 0.3);
        padding: 20px;
    }
    QFrame:hover {
        background-color: rgba(240, 240, 240, 0.5);
        border: 2px dashed rgba(170, 170, 170, 0.8);
    }
    QLabel {
        color: rgba(0, 0, 0, 0.6);
    }
"""

SPINBOX_STYLE = """
    QSpinBox {
        border-radius: 10px;
        padding: 8px;
        background-color: white;
        border: 1px solid #ccc;
        min-width: 80px;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background: #f0f0f0;
        border-left: 1px solid #ccc;
        width: 20px;
    }
    QSpinBox::up-button {
        subcontrol-position: top right;
        border-bottom: 1px solid #ccc;
        border-top-right-radius: 10px;
    }
    QSpinBox::down-button {
        subcontrol-position: bottom right;
        border-bottom-right-radius: 10px;
    }
    QSpinBox::up-arrow {
        width: 10px;
        height: 10px;
        image: url(:/qt-project.org/styles/commonstyle/images/up-arrow.png);
    }
    QSpinBox::down-arrow {
        width: 10px;
        height: 10px;
        image: url(:/qt-project.org/styles/commonstyle/images/down-arrow.png);
    }
"""

class DragDropWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setAcceptDrops(True)
        self.setStyleSheet(DRAG_DROP_STYLE)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        
        self.layout = QVBoxLayout(self)
        self.label = QLabel("Drag & Drop files JPG/JPEG/PNG here\nor click to browse")
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            valid_files = []
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                    valid_files.append(file_path)
            
            if valid_files:
                self.main_window.handle_files_dropped(valid_files)
            else:
                self.main_window.tabs['File']['log_output'].append("❌ No valid image files found")
            
    def mousePressEvent(self, event):
        self.main_window.browse_files()

class ImageProcessor:
    @staticmethod
    def process_images(files, input_dir, max_kb, quality, folder_mode, progress_callback=None):
        """Proses utama untuk kompresi dan rename gambar"""
        results = []
        total_files = len(files)
        
        for idx, file_path in enumerate(files):
            try:
                # Ekstrak informasi path
                dirname = os.path.dirname(file_path)
                filename = os.path.basename(file_path)
                rel_path = os.path.relpath(dirname, input_dir)
                
                # Tentukan prefix berdasarkan mode
                if folder_mode == "multiple":
                    # Untuk multiple folder, gunakan nama level1 folder sebagai prefix
                    level1_folder = rel_path.split(os.sep)[0] if rel_path else ""
                    prefix = level1_folder
                    reduced_base = os.path.join(input_dir, level1_folder, "reduced")
                    rel_output_path = os.path.relpath(dirname, os.path.join(input_dir, level1_folder))
                else:  # single folder
                    # Untuk single folder, gunakan nama folder utama sebagai prefix
                    prefix = os.path.basename(os.path.normpath(input_dir))
                    reduced_base = os.path.join(input_dir, "reduced")
                    rel_output_path = rel_path
                
                # Generate nama file baru
                new_filename = f"{prefix}_{filename}" if prefix else filename
                if not filename.lower().endswith(".jpg"):
                    new_filename = os.path.splitext(new_filename)[0] + ".jpg"
                
                # Buat direktori output
                output_dir = os.path.join(reduced_base, rel_output_path)
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, new_filename)
                
                # Kompresi gambar
                original_size = os.path.getsize(file_path)
                success = ImageProcessor.compress_image(file_path, output_path, max_kb, quality)
                
                if success:
                    new_size = os.path.getsize(output_path)
                    reduction = (original_size - new_size) / original_size * 100
                    
                    results.append({
                        'original': filename,
                        'new': new_filename,
                        'original_size': original_size,
                        'new_size': new_size,
                        'reduction': reduction,
                        'path': output_path
                    })
                    
                    if progress_callback:
                        progress_callback(idx + 1, total_files, f"{filename} → {new_filename}")
                else:
                    results.append({
                        'error': f"Failed to process {filename}"
                    })
                    
            except Exception as e:
                results.append({
                    'error': f"Error processing {filename}: {str(e)}"
                })
                continue
        
        return results

    @staticmethod
    def compress_image(input_path, output_path, max_kb=150, quality=85, max_width=1024):
        """Kompresi gambar dengan ukuran maksimal"""
        try:
            with Image.open(input_path) as img:
                # Konversi ke RGB jika perlu
                if img.mode in ('CMYK', 'LA', 'RGBA'):
                    img = img.convert('RGB')
                
                # Resize jika melebihi max_width
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # Optimasi ukuran dengan iterasi di memory
                buffer = BytesIO()
                optimized = False
                
                for q in range(quality, 30, -5):
                    try:
                        buffer.seek(0)
                        buffer.truncate()
                        img.save(buffer, format='JPEG', quality=q, optimize=True)
                        size_kb = buffer.tell() / 1024
                        
                        if size_kb <= max_kb:
                            # Jika memenuhi, simpan ke file final
                            with open(output_path, 'wb') as f:
                                f.write(buffer.getvalue())
                            optimized = True
                            break
                    except Exception as e:
                        print(f"Temp compression error: {e}")
                        continue
                
                if not optimized:
                    # Jika tidak berhasil optimasi, simpan dengan quality terendah
                    img.save(output_path, format='JPEG', quality=30, optimize=True)
                
                return True
                
        except Exception as e:
            print(f"Compress error: {e}")
            return False

class ImageWorker(QObject):
    progress = Signal(int, int, str)  # (current, total, message)
    result = Signal(dict)             # result dictionary
    finished = Signal()
    
    def __init__(self, files, input_dir, max_kb, quality, folder_mode, prefix=""):
        super().__init__()
        self.files = files
        self.input_dir = input_dir
        self.max_kb = max_kb
        self.quality = quality
        self.folder_mode = folder_mode
        self.prefix = prefix
        self._is_running = True
        
    def process(self):
        try:
            if self.folder_mode == "file":
                results = []
                total_files = len(self.files)
                
                for idx, file_path in enumerate(self.files):
                    if not self._is_running:
                        break
                        
                    try:
                        # Ekstrak informasi file
                        dirname = os.path.dirname(file_path)
                        filename = os.path.basename(file_path)
                        
                        # Buat folder reduced
                        reduced_path = os.path.join(dirname, "reduced")
                        os.makedirs(reduced_path, exist_ok=True)
                        
                        # Generate nama file baru dengan prefix
                        name, ext = os.path.splitext(filename)
                        new_filename = f"{self.prefix}_{filename}" if self.prefix else filename
                        if ext.lower() not in ('.jpg', '.jpeg'):
                            new_filename = os.path.splitext(new_filename)[0] + ".jpg"
                        
                        output_path = os.path.join(reduced_path, new_filename)
                        
                        # Kompresi gambar
                        original_size = os.path.getsize(file_path)
                        success = ImageProcessor.compress_image(file_path, output_path, self.max_kb, self.quality)
                        
                        if success:
                            new_size = os.path.getsize(output_path)
                            reduction = (original_size - new_size) / original_size * 100
                            
                            results.append({
                                'original': filename,
                                'new': new_filename,
                                'original_size': original_size,
                                'new_size': new_size,
                                'reduction': reduction,
                                'path': output_path
                            })
                            
                            self.progress.emit(idx + 1, total_files, f"{filename} → {new_filename}")
                        else:
                            results.append({
                                'error': f"Failed to process {filename}"
                            })
                            
                    except Exception as e:
                        results.append({
                            'error': f"Error processing {filename}: {str(e)}"
                        })
                        continue
            else:
                results = ImageProcessor.process_images(
                    self.files,
                    self.input_dir,
                    self.max_kb,
                    self.quality,
                    self.folder_mode,
                    self._progress_callback
                )
            
            for result in results:
                if 'error' in result:
                    self.result.emit({'error': result['error']})
                else:
                    msg = (f"{result['original']} → {result['new']}\n"
                          f"Size: {result['original_size']/1024:.1f}KB → "
                          f"{result['new_size']/1024:.1f}KB (↓{result['reduction']:.1f}%)\n"
                          f"Saved to: {result['path']}\n")
                    self.result.emit({'success': msg})
            
            self.finished.emit()
        except Exception as e:
            self.result.emit({'error': f"Processing error: {str(e)}"})
            self.finished.emit()
    
    def _progress_callback(self, current, total, message):
        if self._is_running:
            self.progress.emit(current, total, message)
    
    def stop(self):
        self._is_running = False

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Processor")
        self.setMinimumSize(900, 650)
        self.file_paths = []
        self.current_file_index = 0
        self.total_files = 0
        self.worker = None
        self.worker_thread = None

        # Force light palette to prevent dark mode
        self.set_light_palette()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # === Sidebar ===
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(5, 20, 5, 5)
        sidebar_layout.setSpacing(10)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap("logo.png").scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setObjectName("logo_label")
        sidebar_layout.addWidget(logo_label)

        # Tab Buttons
        self.buttons = []
        self.stack = QStackedWidget()
        tab_names = ["Multiple Folder", "Single Folder", "File", "Video"]
        self.tabs = {}

        for i, name in enumerate(tab_names):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda _, idx=i: self.switch_tab(idx))
            sidebar_layout.addWidget(button)
            self.buttons.append(button)

            group = QGroupBox(name)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(10, 15, 10, 15)
            group_layout.setSpacing(10)

            if name in ["Multiple Folder", "Single Folder"]:
                # Folder Input
                folder_layout = QHBoxLayout()
                folder_input = QLineEdit()
                folder_input.setPlaceholderText("Select main folder..." if name == "Multiple Folder" else "Select folder...")
                folder_input.setStyleSheet("border-radius: 10px; padding: 8px; background-color: white; border: 1px solid #ccc;")
                browse_btn = QPushButton("Browse")
                browse_btn.setFixedWidth(80)
                browse_btn.setStyleSheet(BUTTON_STYLE)
                browse_btn.setCursor(Qt.PointingHandCursor)
                browse_btn.clicked.connect(lambda _, n=name: self.browse_folder(n))
                folder_layout.addWidget(folder_input)
                folder_layout.addWidget(browse_btn)
                group_layout.addLayout(folder_layout)
            elif name == "File":
                self.drag_drop = DragDropWidget(self)
                group_layout.addWidget(self.drag_drop)
                
                # File counter
                self.file_counter = QLabel("0 files selected")
                self.file_counter.setAlignment(Qt.AlignCenter)
                group_layout.addWidget(self.file_counter)
            elif name == "Video":
                # Simple "COMING SOON" message for Video tab
                coming_soon = QLabel("COMING SOON")
                coming_soon.setAlignment(Qt.AlignCenter)
                coming_soon.setStyleSheet("font-size: 24px; font-weight: bold; color: #3A3A5A;")
                group_layout.addWidget(coming_soon)
                group_layout.addStretch()

            # Only add controls for non-Video tabs
            if name != "Video":
                # Max Size
                max_size_layout = QHBoxLayout()
                max_size_label = QLabel("Max Size (KB):")
                max_size_input = QSpinBox()
                max_size_input.setRange(1, 5000)
                max_size_input.setValue(150)
                max_size_input.setSuffix(" KB")
                max_size_input.setStyleSheet(SPINBOX_STYLE)
                max_size_layout.addWidget(max_size_label)
                max_size_layout.addWidget(max_size_input)

                # Quality
                quality_layout = QHBoxLayout()
                quality_label = QLabel("Quality:")
                quality_input = QSlider(Qt.Horizontal)
                quality_input.setRange(1, 100)
                quality_input.setValue(85)
                quality_input.setStyleSheet("""
                    QSlider::groove:horizontal {
                        border-radius: 10px;
                        background: #EEE;
                        height: 10px;
                    }
                    QSlider::handle:horizontal {
                        background: #3A3A5A;
                        width: 20px;
                        border-radius: 10px;
                        border: 2px solid #666;
                    }
                    QSlider::sub-page:horizontal {
                        background: #B0BEC5;
                        border-radius: 10px;
                    }
                """)
                quality_input.valueChanged.connect(lambda v, n=name: self.tabs[n]['quality_value'].setText(str(v)))

                quality_value = QLabel("85")
                quality_input.valueChanged.connect(lambda v: quality_value.setText(str(v)))
                quality_layout.addWidget(quality_label)
                quality_layout.addWidget(quality_input)
                quality_layout.addWidget(quality_value)

                # Log Output
                log_output = QTextEdit()
                log_output.setReadOnly(True)
                log_output.setStyleSheet("""
                    QTextEdit {
                        border-radius: 10px;
                        background-color: white;
                        padding: 8px;
                        font-family: Consolas, monospace;
                        border: 1px solid #ccc;
                    }
                """)

                # Progress Bar
                progress_bar = QProgressBar()
                progress_bar.setValue(0)
                progress_bar.setStyleSheet("""
                    QProgressBar {
                        border-radius: 10px;
                        height: 20px;
                        background-color: #EEE;
                        text-align: center;
                        color: #ffd465;
                        border: 1px solid #ccc;
                    }
                    QProgressBar::chunk {
                        border-radius: 10px;
                        background-color: #3A3A5A;
                    }
                """)

                # Buttons
                button_container = QHBoxLayout()
                
                # Start Button
                start_btn = QPushButton("START 🚀")
                start_btn.setFixedHeight(40)
                start_btn.setStyleSheet(BUTTON_STYLE)
                start_btn.setCursor(Qt.PointingHandCursor)
                start_btn.clicked.connect(lambda _, n=name: self.toggle_process(n))
                
                # Stop/Done Button
                stop_done_btn = QPushButton("STOP ⛔")
                stop_done_btn.setFixedHeight(40)
                stop_done_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF5252;
                        color: white;
                        border-radius: 10px;
                        font-size: 14px;
                        padding: 10px 15px;
                    }
                    QPushButton:hover {
                        background-color: #FF0000;
                    }
                    QPushButton:disabled {
                        background-color: #4CAF50;
                        color: white;
                    }
                """)
                stop_done_btn.setCursor(Qt.PointingHandCursor)
                stop_done_btn.clicked.connect(lambda _, n=name: self.toggle_process(n))
                stop_done_btn.setVisible(False)
                
                # Reset Button
                reset_btn = QPushButton("RESET ♻️")
                reset_btn.setFixedHeight(40)
                reset_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1DD35A;
                        color: white;
                        border-radius: 10px;
                        font-size: 14px;
                        padding: 10px 15px;
                    }
                    QPushButton:disabled {
                        background-color: #CFD8DC;
                    }
                """)
                reset_btn.setCursor(Qt.PointingHandCursor)
                reset_btn.clicked.connect(lambda _, n=name: self.reset_process(n))
                reset_btn.setVisible(False)
                reset_btn.setEnabled(False)
                
                # Button Container
                button_container.addWidget(start_btn)
                button_container.addWidget(stop_done_btn)
                button_container.addWidget(reset_btn)
                button_container.setSpacing(10)

                # Layout Assembly
                if name != "File":
                    group_layout.addSpacing(10)
                group_layout.addLayout(max_size_layout)
                group_layout.addSpacing(10)
                group_layout.addLayout(quality_layout)
                group_layout.addSpacing(10)
                group_layout.addLayout(button_container)
                group_layout.addSpacing(10)
                group_layout.addWidget(log_output)
                group_layout.addSpacing(10)
                group_layout.addWidget(progress_bar)

            # Store components
            self.tabs[name] = {
                'group': group,
                'log_output': log_output if name != "Video" else None,
                'progress_bar': progress_bar if name != "Video" else None,
                'start_btn': start_btn if name != "Video" else None,
                'stop_done_btn': stop_done_btn if name != "Video" else None,
                'reset_btn': reset_btn if name != "Video" else None,
                'max_size_input': max_size_input if name != "Video" else None,
                'quality_input': quality_input if name != "Video" else None,
                'quality_value': quality_value if name != "Video" else None,
                'folder_input': folder_input if name in ["Multiple Folder", "Single Folder"] else None,
                'browse_btn': browse_btn if name in ["Multiple Folder", "Single Folder"] else None,
                'drag_drop': self.drag_drop if name == "File" else None,
                'file_counter': self.file_counter if name == "File" else None
            }

            self.stack.addWidget(group)

        sidebar_layout.addStretch()
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setFixedWidth(230)
        sidebar_widget.setObjectName("SidebarWidget")
        sidebar_widget.setStyleSheet("""
            QWidget#SidebarWidget {
                background-color: #325b92;
                border-top-right-radius: 20px;
                border-bottom-right-radius: 20px;
                padding: 10px 5px;
            }
            
            QWidget#SidebarWidget QLabel {
                color: #ffd465;
                padding: 5px;
            }
            
            QWidget#SidebarWidget QPushButton {
                color: #ffd465;
                background-color: transparent;
                text-align: left;
                padding: 8px 15px;
                border-radius: 5px;
                margin: 3px 0;
                border: none;
                font-size: 14px;
            }
            
            QWidget#SidebarWidget QPushButton:hover {
                background-color: rgba(255, 212, 101, 0.15);
                color: white;
            }
            
            QWidget#SidebarWidget QPushButton:checked {
                background-color: rgba(255, 212, 101, 0.25);
                color: #ffd465;
                font-weight: bold;
            }
            
            QWidget#SidebarWidget #logo_label {
                margin-bottom: 15px;
            }
        """)

        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.stack)

        self.switch_tab(0)

    def set_light_palette(self):
        """Force light color palette regardless of system theme"""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(233, 231, 227))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
        palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Link, QColor(0, 0, 255))
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        QApplication.setPalette(palette)

    def __del__(self):
        """Cleanup thread saat window dihancurkan"""
        if hasattr(self, 'worker_thread') and self.worker_thread:
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(500)  # Timeout 500ms

    def is_network_path(self, path):
        """Cek apakah path merupakan network share (hanya untuk folder tab)"""
        if not path:  # Handle empty path
            return False
            
        # Untuk tab File, selalu return False agar bisa akses network share
        current_tab = self.stack.currentWidget().title()
        if current_tab == "File":
            return False
            
        if path.startswith('\\\\'):
            return True
        drive = os.path.splitdrive(path)[0]
        if drive:
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
                return drive_type == 4  # DRIVE_REMOTE
            except:
                return False
        return False

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)

    def browse_folder(self, tab_name):
        """Untuk Multiple/Single Folder tab"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            if self.is_network_path(folder):
                QMessageBox.warning(
                    self,
                    "Akses Ditolak",
                    "Pindah folder neng komputer dewe sek bolo",
                    QMessageBox.Ok
                )
                return
                
            self.tabs[tab_name]['folder_input'].setText(folder)
            if self.tabs[tab_name]['log_output']:
                self.tabs[tab_name]['log_output'].append(f"📂 Selected folder: {folder}")

    def browse_files(self):
        """Untuk File tab - bisa akses network share"""
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Image Files", 
            "", 
            "Image Files (*.jpg *.jpeg *.png)"
        )
        if files:
            self.handle_files_dropped(files)

    def handle_files_dropped(self, file_paths):
        self.file_paths = file_paths
        file_count = len(file_paths)
        if self.tabs['File']['log_output']:
            self.tabs['File']['log_output'].append(f"📄 Selected {file_count} files")
        
        # Update display
        if file_count == 1:
            self.drag_drop.label.setText(f"File selected:\n{file_paths[0].split('/')[-1]}")
        else:
            self.drag_drop.label.setText(f"{file_count} files selected")
        
        if self.tabs['File']['file_counter']:
            self.tabs['File']['file_counter'].setText(f"{file_count} files ready for processing")

    def toggle_process(self, tab_name):
        tab = self.tabs[tab_name]
        if tab_name == "Video":
            return
            
        if tab['start_btn'].isVisible():
            # Start process
            if tab_name == "File":
                # Tampilkan input dialog untuk prefix
                prefix, ok = QInputDialog.getText(
                    self,
                    "File Prefix",
                    "Masukkan prefix untuk nama file:",
                    QLineEdit.Normal,
                    ""
                )
                if not ok:
                    return
                    
                self.process_files_with_prefix(prefix)
            else:
                tab['start_btn'].setVisible(False)
                tab['stop_done_btn'].setVisible(True)
                tab['stop_done_btn'].setText("STOP")
                tab['stop_done_btn'].setEnabled(True)
                tab['reset_btn'].setVisible(True)
                tab['reset_btn'].setEnabled(False)
                self.run_process(tab_name)
        else:
            # Stop process
            if tab['stop_done_btn'].text() == "STOP":
                self.stop_process(tab_name)

    def process_files_with_prefix(self, prefix):
        """Proses khusus untuk tab File dengan prefix"""
        tab = self.tabs['File']
        max_kb = tab['max_size_input'].value()
        quality = tab['quality_input'].value()
        
        if not self.file_paths:
            if tab['log_output']:
                tab['log_output'].append("❌ No files selected!")
            return
            
        # Setup UI
        tab['start_btn'].setVisible(False)
        tab['stop_done_btn'].setVisible(True)
        tab['stop_done_btn'].setText("STOP")
        tab['stop_done_btn'].setEnabled(True)
        tab['reset_btn'].setVisible(True)
        tab['reset_btn'].setEnabled(False)
        tab['progress_bar'].setValue(0)
        if tab['log_output']:
            tab['log_output'].append(f"🟢 Processing {len(self.file_paths)} files with prefix '{prefix}'...")
        
        # Setup worker thread
        self.worker_thread = QThread()
        self.worker = ImageWorker(
            self.file_paths,
            "",  # Tidak perlu input_dir untuk mode file
            max_kb,
            quality,
            "file",  # Mode khusus file
            prefix
        )
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker.progress.connect(partial(self.update_progress, tab))
        self.worker.result.connect(partial(self.handle_result, tab))
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(partial(self.process_completed, tab))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        # Start processing
        self.worker_thread.start()
        QTimer.singleShot(0, self.worker.process)

    def stop_process(self, tab_name):
        tab = self.tabs[tab_name]
        if self.worker:
            self.worker.stop()
        tab['stop_done_btn'].setText("DONE ✔️")
        tab['stop_done_btn'].setEnabled(False)
        tab['reset_btn'].setEnabled(True)
        tab['reset_btn'].setEnabled(True)
        tab['reset_btn'].setEnabled(True)
        if tab['log_output']:
            tab['log_output'].append("⏹ Processing stopped by user")

    def reset_process(self, tab_name):
        tab = self.tabs[tab_name]
        if tab_name == "File":
            self.drag_drop.label.setText("Drag & Drop files JPG/JPEG/PNG here\nor click to browse")
            if tab['file_counter']:
                tab['file_counter'].setText("0 files selected")
            self.file_paths = []
            self.current_file_index = 0
            self.total_files = 0
        else:
            tab['folder_input'].clear()
        
        if tab['max_size_input']:
            tab['max_size_input'].setValue(150)
        if tab['quality_input']:
            tab['quality_input'].setValue(85)
        if tab['progress_bar']:
            tab['progress_bar'].setValue(0)
        if tab['log_output']:
            tab['log_output'].clear()
        
        # Reset button states
        if tab['start_btn']:
            tab['start_btn'].setVisible(True)
        if tab['stop_done_btn']:
            tab['stop_done_btn'].setVisible(False)
        if tab['reset_btn']:
            tab['reset_btn'].setVisible(False)
            tab['reset_btn'].setEnabled(False)

    def run_process(self, tab_name):
        tab = self.tabs[tab_name]
        max_kb = tab['max_size_input'].value()
        quality = tab['quality_input'].value()
        
        folder_mode = "multiple" if tab_name == "Multiple Folder" else "single"
        
        # Setup progress
        tab['progress_bar'].setValue(0)
        
        # Dapatkan folder input
        input_dir = tab['folder_input'].text().strip()
        if not input_dir:
            if tab['log_output']:
                tab['log_output'].append("❌ Folder not selected!")
            return
            
        # Collect image files
        files = []
        for root, _, filenames in os.walk(input_dir):
            for f in filenames:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    files.append(os.path.join(root, f))
    
        total_files = len(files)
        if not total_files:
            if tab['log_output']:
                tab['log_output'].append("❌ No valid images found!")
            return
        
        # Setup worker thread
        self.worker_thread = QThread()
        self.worker = ImageWorker(files, input_dir, max_kb, quality, folder_mode)
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals dengan urutan yang benar
        self.worker.progress.connect(partial(self.update_progress, tab))
        self.worker.result.connect(partial(self.handle_result, tab))
        self.worker.finished.connect(self.worker_thread.quit)  # Ini harus pertama
        self.worker.finished.connect(partial(self.process_completed, tab))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        # Start processing
        if tab['log_output']:
            tab['log_output'].append(f"🟢 Processing {total_files} files in {folder_mode} mode...")
            if folder_mode == "multiple":
                tab['log_output'].append("Output will be saved in 'reduced' folder in each level 1 folder")
            else:
                tab['log_output'].append(f"Output will be saved to: {os.path.join(input_dir, 'reduced')}")
        self.worker_thread.start()
        QTimer.singleShot(0, self.worker.process)

    def update_progress(self, tab, current, total, message):
         progress = int((current / total) * 100)
         if tab['progress_bar']:
            tab['progress_bar'].setValue(progress)
         if tab['log_output']:
            tab['log_output'].append(f"{current}/{total}: {message}")

         if current == total:
            tab['stop_done_btn'].setText("DONE ✔️")
            tab['stop_done_btn'].setEnabled(False)
            tab['reset_btn'].setEnabled(True)


    def handle_result(self, tab, result):
        if 'error' in result and tab['log_output']:
            tab['log_output'].append(f"❌ {result['error']}")
        elif 'success' in result and tab['log_output']:
            tab['log_output'].append(result['success'])

    def process_completed(self, tab):
        if tab['stop_done_btn']:
            tab['stop_done_btn'].setText("DONE ✔️")
            tab['stop_done_btn'].setEnabled(False)
        if tab['reset_btn']:
            tab['reset_btn'].setEnabled(True)
        if tab['log_output']:
            tab['log_output'].append("✅ Processing completed!")
        
        # Reset worker references
        self.worker = None
        self.worker_thread = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Force light style
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())