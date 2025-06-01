import sys
import os
from PyQt6 import QtCore, QtWidgets, QtGui
from PIL import Image, ImageDraw, ImageFont, ImageQt


class ImageViewer(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)  # 修改：默认居中对齐
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)  # 新增：允许接收键盘焦点
        self.pixmap = None
        self.scale_factor = 1.0
        self.offset = QtCore.QPoint(0, 0)
        self.drawing = False
        self.dragging = False  # 新增：拖动状态
        self.drag_start_pos = QtCore.QPoint()  # 新增：拖动起始位置
        self.drag_start_scroll = QtCore.QPoint()  # 新增：拖动起始滚动位置
        self.start_point = QtCore.QPoint()
        self.end_point = QtCore.QPoint()
        self.annotations = []
        self.linked_viewer = None  # 新增：用于链接另一个ImageViewer

    def set_linked_viewer(self, viewer):  # 新增方法
        self.linked_viewer = viewer

    def load_image(self, path):
        image = Image.open(path).convert("RGBA")
        self.original_size = image.size
        self.original_image = image.copy()  # 新增：保存原始图像
        self.image = image.copy()
        self.annotations = []  # 清除旧的标注
        self.scale_factor = 1.0  # 重置缩放比例
        self.update_pixmap()  # 加载图像时仍然居中显示

    def update_pixmap(self, skip_center=False):
        resized_image = self.image.resize(
            (
                int(self.original_size[0] * self.scale_factor),
                int(self.original_size[1] * self.scale_factor),
            ),
            Image.Resampling.LANCZOS,
        )
        qimage = ImageQt.ImageQt(resized_image)
        self.pixmap = QtGui.QPixmap.fromImage(qimage)
        self.setPixmap(self.pixmap)
        self.adjustSize()

        # 只在非缩放操作时进行居中
        if not skip_center:
            parent_scroll_area = None
            if self.parentWidget():
                if self.parentWidget().parentWidget() and isinstance(
                    self.parentWidget().parentWidget(), QtWidgets.QScrollArea
                ):
                    parent_scroll_area = self.parentWidget().parentWidget()

            if parent_scroll_area:
                QtCore.QTimer.singleShot(
                    0, lambda sa=parent_scroll_area: self._center_in_scroll_area(sa)
                )

    def _center_in_scroll_area(self, scroll_area: QtWidgets.QScrollArea):
        """将此ImageViewer的内容在其所在的QScrollArea中居中"""
        h_bar = scroll_area.horizontalScrollBar()
        v_bar = scroll_area.verticalScrollBar()

        content_width = self.width()  # ImageViewer的当前宽度
        viewport_width = scroll_area.viewport().width()

        # 计算水平滚动条的目标位置以居中内容
        # 只有当内容宽度大于视口宽度时才需要滚动
        if content_width > viewport_width:
            target_h_scroll = (content_width - viewport_width) / 2.0
        else:  # 内容宽度小于等于视口宽度，QLabel的AlignCenter会处理居中，滚动条应在最小位置
            target_h_scroll = h_bar.minimum()

        # 确保目标值在滚动条的有效范围内
        target_h_scroll = max(h_bar.minimum(), min(target_h_scroll, h_bar.maximum()))
        h_bar.setValue(int(target_h_scroll))

        content_height = self.height()  # ImageViewer的当前高度
        viewport_height = scroll_area.viewport().height()

        # 计算垂直滚动条的目标位置以居中内容
        if content_height > viewport_height:
            target_v_scroll = (content_height - viewport_height) / 2.0
        else:  # 内容高度小于等于视口高度，滚动条应在最小位置
            target_v_scroll = v_bar.minimum()

        target_v_scroll = max(v_bar.minimum(), min(target_v_scroll, v_bar.maximum()))
        v_bar.setValue(int(target_v_scroll))

    def set_scale_factor_from_link(
        self, new_scale_factor, scroll_ratio=None
    ):  # 新增方法
        """由链接的查看器调用以同步缩放，避免递归触发"""
        if abs(self.scale_factor - new_scale_factor) > 1e-9:
            self.scale_factor = new_scale_factor
            self.update_pixmap(skip_center=True)

            # 如果提供了滚动比例，同步滚动位置
            if scroll_ratio:
                self._sync_scroll_by_ratio(scroll_ratio)

    def _sync_scroll_by_ratio(self, scroll_ratio):
        """根据滚动比例同步滚动条位置"""
        scroll_area = self._get_scroll_area()
        if not scroll_area:
            return

        h_bar = scroll_area.horizontalScrollBar()
        v_bar = scroll_area.verticalScrollBar()

        # 使用 QTimer.singleShot 延迟执行，确保布局更新完成
        QtCore.QTimer.singleShot(
            0, lambda: self._apply_scroll_ratio(h_bar, v_bar, scroll_ratio)
        )

    def _apply_scroll_ratio(self, h_bar, v_bar, scroll_ratio):
        """应用滚动比例"""
        if h_bar.maximum() > 0:
            new_h_value = scroll_ratio["h_ratio"] * h_bar.maximum()
            h_bar.setValue(int(new_h_value))

        if v_bar.maximum() > 0:
            new_v_value = scroll_ratio["v_ratio"] * v_bar.maximum()
            v_bar.setValue(int(new_v_value))

    def _sync_linked_viewer_scroll(self):
        """同步链接查看器的滚动位置"""
        if self.linked_viewer:
            scroll_ratio = self._get_scroll_ratio()
            if scroll_ratio:
                self.linked_viewer._sync_scroll_by_ratio(scroll_ratio)

    def _get_scroll_ratio(self):
        """获取当前滚动条的相对位置比例"""
        scroll_area = self._get_scroll_area()
        if not scroll_area:
            return None

        h_bar = scroll_area.horizontalScrollBar()
        v_bar = scroll_area.verticalScrollBar()

        h_ratio = h_bar.value() / h_bar.maximum() if h_bar.maximum() > 0 else 0
        v_ratio = v_bar.value() / v_bar.maximum() if v_bar.maximum() > 0 else 0

        return {"h_ratio": h_ratio, "v_ratio": v_ratio}

    def _get_scroll_area(self):
        """获取父滚动区域"""
        if self.parentWidget() and self.parentWidget().parentWidget():
            parent = self.parentWidget().parentWidget()
            if isinstance(parent, QtWidgets.QScrollArea):
                return parent
        return None

    def _adjust_scroll_for_zoom(self, old_scale, new_scale, mouse_pos):
        """调整滚动条位置以保持鼠标位置的图像内容不变"""
        scroll_area = self._get_scroll_area()
        if not scroll_area or not self.original_size:
            return

        # 获取鼠标在滚动区域视口中的位置
        viewport_pos = scroll_area.mapFromGlobal(mouse_pos)

        # 获取当前滚动条位置
        h_bar = scroll_area.horizontalScrollBar()
        v_bar = scroll_area.verticalScrollBar()
        old_h_value = h_bar.value()
        old_v_value = v_bar.value()

        # 计算鼠标在旧图像中的绝对位置
        old_mouse_x = old_h_value + viewport_pos.x()
        old_mouse_y = old_v_value + viewport_pos.y()

        # 计算鼠标在原始图像中的相对位置
        old_image_width = self.original_size[0] * old_scale
        old_image_height = self.original_size[1] * old_scale

        if old_image_width > 0 and old_image_height > 0:
            rel_x = old_mouse_x / old_image_width
            rel_y = old_mouse_y / old_image_height

            # 计算鼠标在新图像中的绝对位置
            new_image_width = self.original_size[0] * new_scale
            new_image_height = self.original_size[1] * new_scale

            new_mouse_x = rel_x * new_image_width
            new_mouse_y = rel_y * new_image_height

            # 计算新的滚动条位置
            new_h_value = new_mouse_x - viewport_pos.x()
            new_v_value = new_mouse_y - viewport_pos.y()

            # 设置滚动条位置
            h_bar.setValue(int(max(0, min(new_h_value, h_bar.maximum()))))
            v_bar.setValue(int(max(0, min(new_v_value, v_bar.maximum()))))

    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y()
        old_scale_factor = self.scale_factor

        if delta > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1

        if abs(self.scale_factor - old_scale_factor) > 1e-9:  # 比较浮点数
            # 获取鼠标的全局位置
            mouse_pos = event.globalPosition().toPoint()

            # 更新图像但跳过自动居中
            self.update_pixmap(skip_center=True)

            # 调整滚动位置以保持鼠标位置的内容不变
            self._adjust_scroll_for_zoom(old_scale_factor, self.scale_factor, mouse_pos)

            # 同步链接的查看器 - 使用滚动比例而不是鼠标位置
            if self.linked_viewer:
                scroll_ratio = self._get_scroll_ratio()
                self.linked_viewer.set_scale_factor_from_link(
                    self.scale_factor, scroll_ratio
                )

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # 新增：点击时获取焦点以接收键盘事件
        self.setFocus()

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            # 开始拖动
            self.dragging = True
            self.drag_start_pos = event.globalPosition().toPoint()  # 使用全局坐标
            scroll_area = self._get_scroll_area()
            if scroll_area:
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                self.drag_start_scroll = QtCore.QPoint(h_bar.value(), v_bar.value())
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.drawing:
            self.end_point = event.pos()
            self.repaint()
        elif self.dragging:
            # 处理拖动 - 使用全局坐标避免抖动
            scroll_area = self._get_scroll_area()
            if scroll_area:
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()

                # 使用全局坐标计算移动距离
                current_global_pos = event.globalPosition().toPoint()
                delta = self.drag_start_pos - current_global_pos

                # 设置新的滚动位置
                new_h = self.drag_start_scroll.x() + delta.x()
                new_v = self.drag_start_scroll.y() + delta.y()

                # 限制在有效范围内
                new_h = max(h_bar.minimum(), min(new_h, h_bar.maximum()))
                new_v = max(v_bar.minimum(), min(new_v, v_bar.maximum()))

                h_bar.setValue(int(new_h))
                v_bar.setValue(int(new_v))

                # 同步链接的查看器
                self._sync_linked_viewer_scroll()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            rect = QtCore.QRect(self.start_point, self.end_point).normalized()
            text, ok = QtWidgets.QInputDialog.getText(
                self, "问题描述", "请输入问题描述："
            )
            if ok and text:
                self.annotations.append((rect, text))
                self.redraw_annotations()
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton and self.dragging:
            # 结束拖动
            self.dragging = False
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def enterEvent(self, event):
        """鼠标进入控件时设置光标"""
        if not self.dragging:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开控件时重置光标"""
        if not self.dragging:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def redraw_annotations(self):
        draw = ImageDraw.Draw(self.image)
        font = ImageFont.load_default()
        for rect, text in self.annotations:
            x1 = rect.topLeft().x() / self.scale_factor
            y1 = rect.topLeft().y() / self.scale_factor
            x2 = rect.bottomRight().x() / self.scale_factor
            y2 = rect.bottomRight().y() / self.scale_factor
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1, y1 - 15), text, fill="red", font=font)
        self.update_pixmap(skip_center=True)  # 修改：跳过居中

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drawing and self.pixmap:
            # 使用临时绘制，不修改原始 pixmap
            painter = QtGui.QPainter(self)
            painter.setPen(
                QtGui.QPen(QtCore.Qt.GlobalColor.red, 2, QtCore.Qt.PenStyle.DashLine)
            )
            rect = QtCore.QRect(self.start_point, self.end_point)
            painter.drawRect(rect)
            painter.end()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """处理键盘事件"""
        if (
            event.key() == QtCore.Qt.Key.Key_Z
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.undo_last_annotation()
        else:
            super().keyPressEvent(event)

    def undo_last_annotation(self):
        """撤销最后一个标注"""
        if self.annotations:
            self.annotations.pop()  # 移除最后一个标注
            self.redraw_all_annotations()  # 重新绘制所有标注

    def redraw_all_annotations(self):
        """重新绘制所有标注（从原始图像开始）"""
        if hasattr(self, "original_image"):
            # 重新从原始图像开始
            self.image = self.original_image.copy()

        # 重新绘制所有剩余的标注
        draw = ImageDraw.Draw(self.image)
        font = ImageFont.load_default()
        for rect, text in self.annotations:
            x1 = rect.topLeft().x() / self.scale_factor
            y1 = rect.topLeft().y() / self.scale_factor
            x2 = rect.bottomRight().x() / self.scale_factor
            y2 = rect.bottomRight().y() / self.scale_factor
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1, y1 - 15), text, fill="red", font=font)
        self.update_pixmap(skip_center=True)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图像审核与标注工具")
        self.setGeometry(100, 100, 1200, 600)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # 路径选择区域
        path_widget = QtWidgets.QWidget()
        path_main_layout = QtWidgets.QVBoxLayout(path_widget)

        self.source_path = QtWidgets.QLineEdit()
        self.target_path = QtWidgets.QLineEdit()
        btn_source = QtWidgets.QPushButton("选择原图")
        btn_target = QtWidgets.QPushButton("选择成品")

        btn_source.clicked.connect(lambda: self.select_folder(self.source_path))
        btn_target.clicked.connect(lambda: self.select_folder(self.target_path))

        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(QtWidgets.QLabel("原图路径："))
        path_layout.addWidget(self.source_path)
        path_layout.addWidget(btn_source)

        path_layout2 = QtWidgets.QHBoxLayout()
        path_layout2.addWidget(QtWidgets.QLabel("成品路径："))
        path_layout2.addWidget(self.target_path)
        path_layout2.addWidget(btn_target)

        path_main_layout.addLayout(path_layout)
        path_main_layout.addLayout(path_layout2)

        # 图片查看器区域 - 左右布局
        image_widget = QtWidgets.QWidget()
        image_layout = QtWidgets.QHBoxLayout(image_widget)

        self.viewer1 = ImageViewer()
        self.viewer2 = ImageViewer()

        # 链接两个查看器
        self.viewer1.set_linked_viewer(self.viewer2)
        self.viewer2.set_linked_viewer(self.viewer1)

        # 为每个查看器添加滚动区域
        scroll1 = QtWidgets.QScrollArea()
        scroll1.setWidget(self.viewer1)
        scroll1.setWidgetResizable(True)
        scroll1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        scroll2 = QtWidgets.QScrollArea()
        scroll2.setWidget(self.viewer2)
        scroll2.setWidgetResizable(True)
        scroll2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # 添加标题
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.addWidget(QtWidgets.QLabel("原图"))
        left_layout.addWidget(scroll1)

        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.addWidget(QtWidgets.QLabel("成品"))
        right_layout.addWidget(scroll2)

        image_layout.addWidget(left_panel)
        image_layout.addWidget(right_panel)

        # 导航按钮区域
        nav_widget = QtWidgets.QWidget()
        nav_layout = QtWidgets.QHBoxLayout(nav_widget)
        self.prev_btn = QtWidgets.QPushButton("上一张")
        self.next_btn = QtWidgets.QPushButton("下一张")
        export_btn = QtWidgets.QPushButton("导出当前图片")
        self.prev_btn.clicked.connect(self.prev_image)
        self.next_btn.clicked.connect(self.next_image)
        export_btn.clicked.connect(self.export_current)

        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(export_btn)

        # 添加到主布局
        main_layout.addWidget(path_widget)
        main_layout.addWidget(image_widget, stretch=1)  # 图片区域占主要空间
        main_layout.addWidget(nav_widget)

        self.image_files = []
        self.current_index = 0

    def select_folder(self, line_edit):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            line_edit.setText(folder)
            self.load_images()

    def load_images(self):
        source = self.source_path.text()
        target = self.target_path.text()
        if not os.path.isdir(source) or not os.path.isdir(target):
            return
        source_files = set(os.listdir(source))
        target_files = set(os.listdir(target))
        common_files = sorted(list(source_files & target_files))
        self.image_files = [
            (os.path.join(source, f), os.path.join(target, f)) for f in common_files
        ]
        self.current_index = 0
        self.show_current()

    def show_current(self):
        if not self.image_files:
            return
        src, tgt = self.image_files[self.current_index]
        self.viewer1.load_image(src)
        self.viewer2.load_image(tgt)
        self.update_nav_buttons()

    def update_nav_buttons(self):
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current()

    def next_image(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_current()

    def export_current(self):
        viewer = self.viewer2
        if viewer.image and self.image_files:
            # 获取当前图片信息
            src_path, tgt_path = self.image_files[self.current_index]
            original_filename = os.path.basename(src_path)
            name, ext = os.path.splitext(original_filename)

            # 构造新文件名
            new_filename = f"已审核_{name}{ext}"

            # 构造保存路径（保存到成品目录）
            target_dir = self.target_path.text()
            if not target_dir:
                QtWidgets.QMessageBox.warning(self, "警告", "请先选择成品路径")
                return

            save_path = os.path.join(target_dir, new_filename)

            # 如果文件已存在，询问是否覆盖
            if os.path.exists(save_path):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "文件已存在",
                    f"文件 {new_filename} 已存在，是否覆盖？",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                )
                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    return

            try:
                # 处理图像格式转换
                image_to_save = viewer.image
                file_ext = ext.lower()

                # 如果是 JPEG 格式且图像是 RGBA 模式，需要转换为 RGB
                if file_ext in [".jpg", ".jpeg"] and image_to_save.mode == "RGBA":
                    # 创建白色背景
                    rgb_image = Image.new("RGB", image_to_save.size, (255, 255, 255))
                    # 将 RGBA 图像粘贴到白色背景上
                    rgb_image.paste(
                        image_to_save, mask=image_to_save.split()[-1]
                    )  # 使用 alpha 通道作为蒙版
                    image_to_save = rgb_image

                image_to_save.save(save_path)
                QtWidgets.QMessageBox.information(
                    self, "成功", f"图片已保存到：{save_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
