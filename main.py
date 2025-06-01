# -*- coding: utf-8 -*-
# 本地漫画汉化审核工具 - 方案A：PyQt5 + OpenCV

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog,
    QHBoxLayout, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSlider, QTextEdit, QCheckBox
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QPoint
import cv2

class ImageCompareView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.scale_factor = 1.0
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def load_image(self, path):
        image = QImage(path)
        self.pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(self.scene.itemsBoundingRect())

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0
        factor = 1.25 if zoom_in else 0.8
        self.scale(factor, factor)
        self.scale_factor *= factor

class ReviewTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("漫画汉化审核工具")
        self.resize(1400, 800)

        self.original_folder = ""
        self.translated_folder = ""
        self.image_names = []
        self.current_index = 0

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        folder_layout = QHBoxLayout()

        self.orig_btn = QPushButton("选择原图文件夹")
        self.trans_btn = QPushButton("选择汉化图文件夹")
        self.prev_btn = QPushButton("← 上一页")
        self.next_btn = QPushButton("下一页 →")

        self.orig_btn.clicked.connect(self.select_orig_folder)
        self.trans_btn.clicked.connect(self.select_trans_folder)
        self.prev_btn.clicked.connect(self.prev_image)
        self.next_btn.clicked.connect(self.next_image)

        folder_layout.addWidget(self.orig_btn)
        folder_layout.addWidget(self.trans_btn)
        folder_layout.addWidget(self.prev_btn)
        folder_layout.addWidget(self.next_btn)

        self.orig_view = ImageCompareView()
        self.trans_view = ImageCompareView()

        img_layout = QHBoxLayout()
        img_layout.addWidget(self.orig_view)
        img_layout.addWidget(self.trans_view)

        self.need_fix_checkbox = QCheckBox("此页需修改")
        self.comment_box = QTextEdit()
        self.comment_box.setPlaceholderText("问题说明，如翻译错误、字体模糊等...")

        layout.addLayout(folder_layout)
        layout.addLayout(img_layout)
        layout.addWidget(self.need_fix_checkbox)
        layout.addWidget(self.comment_box)

        self.setLayout(layout)

    def select_orig_folder(self):
        self.original_folder = QFileDialog.getExistingDirectory(self, "选择原图文件夹")
        self.update_file_list()

    def select_trans_folder(self):
        self.translated_folder = QFileDialog.getExistingDirectory(self, "选择汉化图文件夹")
        self.update_file_list()

    def update_file_list(self):
        if self.original_folder and self.translated_folder:
            orig_names = sorted(os.listdir(self.original_folder))
            trans_names = sorted(os.listdir(self.translated_folder))
            # 只保留两边都有的图
            self.image_names = [name for name in orig_names if name in trans_names]
            self.current_index = 0
            self.load_images()

    def load_images(self):
        if not self.image_names:
            return
        name = self.image_names[self.current_index]
        orig_path = os.path.join(self.original_folder, name)
        trans_path = os.path.join(self.translated_folder, name)
        self.orig_view.load_image(orig_path)
        self.trans_view.load_image(trans_path)
        self.setWindowTitle(f"漫画汉化审核工具 - 当前页: {name} ({self.current_index+1}/{len(self.image_names)})")

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_images()

    def next_image(self):
        if self.current_index < len(self.image_names) - 1:
            self.current_index += 1
            self.load_images()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ReviewTool()
    win.show()
    sys.exit(app.exec_())
