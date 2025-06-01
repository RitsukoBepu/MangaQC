import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                            QVBoxLayout, QPushButton, QFileDialog, QLabel, 
                            QSplitter, QGraphicsView, QGraphicsScene,
                            QGraphicsRectItem, QInputDialog, QToolBar, 
                            QAction, QMessageBox, QCheckBox, QListWidget)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QTransform
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal, QObject, QDateTime

class SyncedGraphicsView(QGraphicsView):
    """同步的图形视图，可与其他视图同步操作"""
    transformChanged = pyqtSignal(QTransform)
    scrollBarChanged = pyqtSignal(str, int)  # 方向, 值
    annotationAdded = pyqtSignal(str)  # 新增：标注添加信号，参数为标注文本
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setInteractive(True)
        self.is_syncing = False
        self.annotation_mode = False
        self.annotation_start = None
        self.current_annotation = None
        self.annotations = []
        
        # 启用水平和垂直滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 连接滚动条信号
        self.horizontalScrollBar().valueChanged.connect(self.onHorizontalScroll)
        self.verticalScrollBar().valueChanged.connect(self.onVerticalScroll)
        
    def onHorizontalScroll(self, value):
        """处理水平滚动条变化"""
        if not self.is_syncing:
            self.scrollBarChanged.emit("horizontal", value)
            
    def onVerticalScroll(self, value):
        """处理垂直滚动条变化"""
        if not self.is_syncing:
            self.scrollBarChanged.emit("vertical", value)
        
    def wheelEvent(self, event):
        """处理鼠标滚轮缩放"""
        # 计算缩放因子
        factor = 1.1
        if event.angleDelta().y() < 0:
            factor = 0.9
            
        # 执行缩放
        self.scale(factor, factor)
        
        # 如果不是正在同步中，发送变换矩阵变化信号
        if not self.is_syncing:
            self.transformChanged.emit(self.transform())
        
    def syncTransform(self, transform):
        """与配对视图同步变换矩阵"""
        self.is_syncing = True
        # 使用完全相同的变换矩阵
        self.setTransform(transform)
        self.is_syncing = False
        
    def syncScrollBar(self, orientation, value):
        """同步滚动条位置"""
        self.is_syncing = True
        if orientation == "horizontal":
            # 获取目标百分比位置
            source_max = self.sender().horizontalScrollBar().maximum()
            if source_max > 0:  # 避免除以零
                percent = value / source_max
                # 应用到当前视图的滚动条
                my_max = self.horizontalScrollBar().maximum()
                new_value = int(percent * my_max)
                self.horizontalScrollBar().setValue(new_value)
        else:  # vertical
            # 获取目标百分比位置
            source_max = self.sender().verticalScrollBar().maximum()
            if source_max > 0:  # 避免除以零
                percent = value / source_max
                # 应用到当前视图的滚动条
                my_max = self.verticalScrollBar().maximum()
                new_value = int(percent * my_max)
                self.verticalScrollBar().setValue(new_value)
        self.is_syncing = False
        
    def scrollContentsBy(self, dx, dy):
        """重写以捕获移动并同步"""
        super().scrollContentsBy(dx, dy)
        if not self.is_syncing:
            # 不使用transform信号，因为它不总是能反映滚动条变化
            # 滚动条的值变化已经通过专门的信号处理
            pass
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件用于标注"""
        if self.annotation_mode and event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.pos())
            self.annotation_start = pos
            self.current_annotation = QGraphicsRectItem(QRectF(pos, QSizeF(1, 1)))
            self.current_annotation.setPen(QPen(Qt.red, 2))
            self.scene().addItem(self.current_annotation)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件用于标注"""
        if self.annotation_mode and self.annotation_start and self.current_annotation:
            pos = self.mapToScene(event.pos())
            rect = QRectF(self.annotation_start, pos).normalized()
            self.current_annotation.setRect(rect)
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件用于标注"""
        if self.annotation_mode and event.button() == Qt.LeftButton and self.current_annotation:
            end_pos = self.mapToScene(event.pos())
            rect = QRectF(self.annotation_start, end_pos).normalized()
            
            # 仅当矩形有一定大小时才创建标注
            if rect.width() > 5 and rect.height() > 5:
                # 添加标注文本
                text, ok = QInputDialog.getText(self, "标注", "输入标注文本:")
                if ok and text:
                    text_item = self.scene().addText(text)
                    text_item.setPos(rect.topLeft())
                    text_item.setDefaultTextColor(Qt.red)
                    self.annotations.append((self.current_annotation, text_item))
                    
                    # 发出标注添加信号
                    self.annotationAdded.emit(text)
                else:
                    self.scene().removeItem(self.current_annotation)
            else:
                self.scene().removeItem(self.current_annotation)
                
            self.current_annotation = None
            self.annotation_start = None
        else:
            super().mouseReleaseEvent(event)


class ImageComparisonTool(QMainWindow):
    """主应用程序窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("翻译质量检查图像对比工具")
        self.resize(1200, 800)
        
        # 数据
        self.original_folder = ""
        self.translated_folder = ""
        self.annotation_folder = ""  # 新增：标注文件夹路径
        self.image_pairs = []  # 存储图像对的列表，每个元素是(原始图像路径,翻译图像路径)
        self.current_index = -1
        self.modified_images = set()
        
        # 界面设置
        self.setup_ui()
        
        # 添加调试信息
        print("程序已启动")
        print(f"用户登录名: Juggernautsst")
        print(f"当前日期时间: {QDateTime.currentDateTimeUtc().toString('yyyy-MM-dd HH:mm:ss')}")
        
    def setup_ui(self):
        """设置用户界面"""
        # 主部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧导航面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(250)
        
        # 文件夹选择按钮
        select_folders_btn = QPushButton("选择图像文件夹")
        select_folders_btn.clicked.connect(self.select_image_folders)
        left_layout.addWidget(select_folders_btn)
        
        # 标注文件夹选择按钮
        select_annotation_folder_btn = QPushButton("选择标注保存文件夹")
        select_annotation_folder_btn.clicked.connect(self.select_annotation_folder)
        left_layout.addWidget(select_annotation_folder_btn)
        
        # 图像列表
        self.image_list = QListWidget()
        self.image_list.currentRowChanged.connect(self.on_image_selected)
        left_layout.addWidget(QLabel("图像列表:"))
        left_layout.addWidget(self.image_list)
        
        # 导航按钮
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("上一章")
        self.prev_button.clicked.connect(self.prev_image)
        nav_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("下一章")
        self.next_button.clicked.connect(self.next_image)
        nav_layout.addWidget(self.next_button)
        
        left_layout.addLayout(nav_layout)
        
        # 修改状态复选框
        self.modified_checkbox = QCheckBox("需要修改")
        self.modified_checkbox.stateChanged.connect(self.modified_checkbox_changed)
        left_layout.addWidget(self.modified_checkbox)
        
        # 导出按钮
        export_btn = QPushButton("导出带标注的图像")
        export_btn.clicked.connect(self.export_annotated_images)
        left_layout.addWidget(export_btn)
        
        # 将左侧面板添加到主布局
        main_layout.addWidget(left_panel)
        
        # 右侧图像视图
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 标注按钮
        self.annotation_button = QPushButton("切换标注模式")
        self.annotation_button.setCheckable(True)
        self.annotation_button.clicked.connect(self.toggle_annotation)
        toolbar_layout.addWidget(self.annotation_button)
        
        # 缩放控制按钮
        zoom_in_btn = QPushButton("放大")
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("缩小")
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar_layout.addWidget(zoom_out_btn)
        
        # 重置视图按钮
        reset_view_btn = QPushButton("重置视图")
        reset_view_btn.clicked.connect(self.reset_views)
        toolbar_layout.addWidget(reset_view_btn)
        
        # 手动保存当前标注按钮
        save_annotation_btn = QPushButton("保存当前标注")
        save_annotation_btn.clicked.connect(self.save_current_annotation)
        toolbar_layout.addWidget(save_annotation_btn)
        
        # 添加工具栏到布局
        right_layout.addLayout(toolbar_layout)
        
        # 图像视图
        image_splitter = QSplitter(Qt.Horizontal)
        
        # 原始图像视图
        self.original_scene = QGraphicsScene()
        self.original_view = SyncedGraphicsView(self.original_scene)
        self.original_container = QWidget()
        original_layout = QVBoxLayout(self.original_container)
        original_layout.addWidget(QLabel("原始图像 (使用鼠标滚轮缩放，拖动平移，或使用滚动条)"))
        original_layout.addWidget(self.original_view)
        image_splitter.addWidget(self.original_container)
        
        # 翻译图像视图
        self.translated_scene = QGraphicsScene()
        self.translated_view = SyncedGraphicsView(self.translated_scene)
        self.translated_container = QWidget()
        translated_layout = QVBoxLayout(self.translated_container)
        translated_layout.addWidget(QLabel("翻译图像 (使用鼠标滚轮缩放，拖动平移，或使用滚动条)"))
        translated_layout.addWidget(self.translated_view)
        image_splitter.addWidget(self.translated_container)
        
        # 连接变换同步信号
        self.original_view.transformChanged.connect(self.translated_view.syncTransform)
        self.translated_view.transformChanged.connect(self.original_view.syncTransform)
        
        # 连接滚动条同步信号
        self.original_view.scrollBarChanged.connect(self.translated_view.syncScrollBar)
        self.translated_view.scrollBarChanged.connect(self.original_view.syncScrollBar)
        
        # 连接标注添加信号
        self.original_view.annotationAdded.connect(self.on_annotation_added)
        self.translated_view.annotationAdded.connect(self.on_annotation_added)
        
        right_layout.addWidget(image_splitter)
        
        # 状态栏
        self.status_label = QLabel("请选择图像文件夹")
        self.statusBar().addWidget(self.status_label)
        
        # 将右侧面板添加到主布局
        main_layout.addWidget(right_panel)
        
        # 初始禁用导航按钮
        self.update_navigation()
    
    def select_annotation_folder(self):
        """选择标注文件保存文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择标注保存文件夹", "")
        if folder:
            self.annotation_folder = folder
            self.status_label.setText(f"标注将保存到: {folder}")
            print(f"已选择标注保存文件夹: {folder}")
    
    def on_annotation_added(self, annotation_text):
        """当添加标注时自动保存图像"""
        self.save_current_annotation(annotation_text)
    
    def save_current_annotation(self, annotation_text=None):
        """保存当前带标注的图像"""
        if self.current_index < 0 or self.current_index >= len(self.image_pairs):
            QMessageBox.warning(self, "保存失败", "没有当前图像可保存")
            return
            
        # 如果没有设置标注文件夹，使用与原始图像相同的文件夹创建子文件夹
        if not self.annotation_folder:
            _, _, filename = self.image_pairs[self.current_index]
            parent_folder = os.path.dirname(self.original_folder)
            self.annotation_folder = os.path.join(parent_folder, "标注")
            
        # 确保标注文件夹存在
        os.makedirs(self.annotation_folder, exist_ok=True)
        
        try:
            # 获取当前图像信息
            _, _, filename = self.image_pairs[self.current_index]
            
            # 创建文件名：原始文件名_标注_时间戳.扩展名
            base_name, ext = os.path.splitext(filename)
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
            
            if annotation_text:
                # 使用前20个字符作为文件名的一部分，移除非法字符
                annotation_short = ''.join(c for c in annotation_text[:20] if c.isalnum() or c in ' _-')
                annotation_short = annotation_short.replace(' ', '_')
                new_filename = f"{base_name}_标注_{annotation_short}_{timestamp}{ext}"
            else:
                new_filename = f"{base_name}_标注_{timestamp}{ext}"
            
            output_path = os.path.join(self.annotation_folder, new_filename)
            
            # 保存原始图像带标注
            if self.original_view.annotations:
                orig_image = QImage(self.original_scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                orig_image.fill(Qt.white)
                painter = QPainter(orig_image)
                self.original_scene.render(painter)
                painter.end()
                orig_image.save(os.path.join(self.annotation_folder, f"orig_{new_filename}"))
                
            # 保存翻译图像带标注
            if self.translated_view.annotations:
                trans_image = QImage(self.translated_scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                trans_image.fill(Qt.white)
                painter = QPainter(trans_image)
                self.translated_scene.render(painter)
                painter.end()
                trans_image.save(output_path)
                
            # 如果两个视图都没有标注，给出提示
            if not self.original_view.annotations and not self.translated_view.annotations:
                QMessageBox.information(self, "没有标注", "当前图像没有添加任何标注")
                return
                
            self.status_label.setText(f"已保存标注图像到: {output_path}")
            print(f"已保存标注图像: {output_path}")
                
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存标注图像时出错: {str(e)}")
            print(f"保存标注图像时出错: {str(e)}")
    
    def zoom_in(self):
        """放大两个视图"""
        factor = 1.2
        self.original_view.scale(factor, factor)
        self.translated_view.scale(factor, factor)
        
    def zoom_out(self):
        """缩小两个视图"""
        factor = 0.8
        self.original_view.scale(factor, factor)
        self.translated_view.scale(factor, factor)
        
    def reset_views(self):
        """重置两个视图的缩放和位置"""
        # 重置变换
        self.original_view.resetTransform()
        self.translated_view.resetTransform()
        
        # 重置滚动条位置
        self.original_view.horizontalScrollBar().setValue(0)
        self.original_view.verticalScrollBar().setValue(0)
        self.translated_view.horizontalScrollBar().setValue(0)
        self.translated_view.verticalScrollBar().setValue(0)
        
        # 调整视图以适应内容
        if not self.original_scene.items():
            return
            
        self.original_view.fitInView(self.original_scene.sceneRect(), Qt.KeepAspectRatio)
        self.translated_view.fitInView(self.translated_scene.sceneRect(), Qt.KeepAspectRatio)
    
    def select_image_folders(self):
        """选择包含原始图像和翻译图像的文件夹"""
        # 选择原始图像文件夹
        original_folder = QFileDialog.getExistingDirectory(self, "选择原始图像文件夹", "")
        if not original_folder:
            return
            
        # 选择翻译图像文件夹
        translated_folder = QFileDialog.getExistingDirectory(self, "选择翻译图像文件夹", "")
        if not translated_folder:
            return
            
        self.original_folder = original_folder
        self.translated_folder = translated_folder
        
        # 如果没有选择标注文件夹，默认在原始图像文件夹旁边创建"标注"文件夹
        if not self.annotation_folder:
            parent_folder = os.path.dirname(original_folder)
            self.annotation_folder = os.path.join(parent_folder, "标注")
        
        # 查找匹配的图像对
        self.find_image_pairs()
    
    def find_image_pairs(self):
        """在选定的文件夹中查找匹配的图像对"""
        self.image_pairs = []
        self.image_list.clear()
        
        if not self.original_folder or not self.translated_folder:
            return
            
        # 获取原始文件夹中的所有图像文件
        original_images = [f for f in os.listdir(self.original_folder) 
                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))]
        
        # 获取翻译文件夹中的所有图像文件
        translated_images = [f for f in os.listdir(self.translated_folder) 
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))]
        
        # 找出两个文件夹中文件名相同的图像
        matching_filenames = set(original_images) & set(translated_images)
        
        # 创建图像对
        for filename in sorted(matching_filenames):
            original_path = os.path.join(self.original_folder, filename)
            translated_path = os.path.join(self.translated_folder, filename)
            
            # 检查图像尺寸是否相同
            orig_img = QImage(original_path)
            trans_img = QImage(translated_path)
            
            if orig_img.size() == trans_img.size():
                self.image_pairs.append((original_path, translated_path, filename))
                self.image_list.addItem(filename)
            else:
                print(f"警告: 图像 {filename} 的尺寸不匹配，原始尺寸: {orig_img.size()}, 翻译尺寸: {trans_img.size()}")
        
        # 更新状态
        if self.image_pairs:
            self.status_label.setText(f"找到 {len(self.image_pairs)} 对匹配的图像")
            self.current_index = 0
            self.image_list.setCurrentRow(0)
            self.load_current_image_pair()
        else:
            self.status_label.setText("未找到匹配的图像对")
        
        # 更新导航按钮状态
        self.update_navigation()
    
    def on_image_selected(self, row):
        """当在列表中选择图像时调用"""
        if row >= 0 and row < len(self.image_pairs):
            self.current_index = row
            self.load_current_image_pair()
            self.update_navigation()
    
    def load_current_image_pair(self):
        """加载当前选择的图像对"""
        if self.current_index < 0 or self.current_index >= len(self.image_pairs):
            return
            
        original_path, translated_path, filename = self.image_pairs[self.current_index]
        
        try:
            # 加载原始图像
            original_pixmap = QPixmap(original_path)
            if original_pixmap.isNull():
                self.status_label.setText(f"无法加载原始图像: {filename}")
                return
                
            self.original_scene.clear()
            self.original_scene.addPixmap(original_pixmap)
            self.original_scene.setSceneRect(0, 0, original_pixmap.width(), original_pixmap.height())
            
            # 加载翻译图像
            translated_pixmap = QPixmap(translated_path)
            if translated_pixmap.isNull():
                self.status_label.setText(f"无法加载翻译图像: {filename}")
                return
                
            self.translated_scene.clear()
            self.translated_scene.addPixmap(translated_pixmap)
            self.translated_scene.setSceneRect(0, 0, translated_pixmap.width(), translated_pixmap.height())
            
            # 确保两个视图的场景大小一致
            self.original_view.setSceneRect(self.original_scene.sceneRect())
            self.translated_view.setSceneRect(self.translated_scene.sceneRect())
            
            # 清空标注列表
            self.original_view.annotations = []
            self.translated_view.annotations = []
            
            # 重置视图
            self.reset_views()
            
            # 更新修改状态复选框
            self.modified_checkbox.setChecked(filename in self.modified_images)
            
            # 更新状态栏
            self.status_label.setText(f"当前图像: {filename} ({self.current_index + 1}/{len(self.image_pairs)})")
            
            # 更新窗口标题
            self.setWindowTitle(f"翻译质量检查工具 - {filename}")
            
            # 输出图像尺寸信息
            print(f"加载图像: {filename}")
            print(f"原始图像尺寸: {original_pixmap.width()}x{original_pixmap.height()}")
            print(f"翻译图像尺寸: {translated_pixmap.width()}x{translated_pixmap.height()}")
            
        except Exception as e:
            self.status_label.setText(f"加载图像时出错: {str(e)}")
            print(f"加载图像时出错: {str(e)}")
    
    def next_image(self):
        """切换到下一对图像"""
        if self.current_index < len(self.image_pairs) - 1:
            self.current_index += 1
            self.image_list.setCurrentRow(self.current_index)
            self.load_current_image_pair()
            self.update_navigation()
            print(f"切换到下一张图像: {self.current_index + 1}/{len(self.image_pairs)}")
    
    def prev_image(self):
        """切换到上一对图像"""
        if self.current_index > 0:
            self.current_index -= 1
            self.image_list.setCurrentRow(self.current_index)
            self.load_current_image_pair()
            self.update_navigation()
            print(f"切换到上一张图像: {self.current_index + 1}/{len(self.image_pairs)}")
    
    def update_navigation(self):
        """更新导航按钮状态"""
        has_images = len(self.image_pairs) > 0
        self.prev_button.setEnabled(has_images and self.current_index > 0)
        self.next_button.setEnabled(has_images and self.current_index < len(self.image_pairs) - 1)
    
    def toggle_annotation(self, checked):
        """切换标注模式"""
        self.original_view.annotation_mode = checked
        self.translated_view.annotation_mode = checked
        
        if checked:
            self.statusBar().showMessage("标注模式：开启 - 绘制矩形以标记问题")
        else:
            self.statusBar().showMessage("标注模式：关闭")
    
    def modified_checkbox_changed(self, state):
        """处理修改状态复选框状态变化"""
        if self.current_index < 0 or self.current_index >= len(self.image_pairs):
            return
            
        _, _, filename = self.image_pairs[self.current_index]
        
        if state == Qt.Checked:
            self.modified_images.add(filename)
            print(f"标记图像为需要修改: {filename}")
        else:
            if filename in self.modified_images:
                self.modified_images.remove(filename)
                print(f"取消标记图像为需要修改: {filename}")
    
    def export_annotated_images(self):
        """将带标注的图像导出到文件夹"""
        if not self.image_pairs:
            QMessageBox.warning(self, "导出错误", "没有图像可导出")
            return
            
        export_folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if not export_folder:
            return
            
        try:
            # 创建子文件夹
            needs_modification_folder = os.path.join(export_folder, "需要修改")
            approved_folder = os.path.join(export_folder, "已通过")
            
            os.makedirs(needs_modification_folder, exist_ok=True)
            os.makedirs(approved_folder, exist_ok=True)
            
            # 保存当前索引以便稍后恢复
            current = self.current_index
            
            # 处理所有图像对
            for i, (original_path, translated_path, filename) in enumerate(self.image_pairs):
                # 切换到当前图像对
                self.current_index = i
                self.load_current_image_pair()
                
                # 确定目标文件夹
                target_folder = needs_modification_folder if filename in self.modified_images else approved_folder
                
                # 原始图像
                orig_image = QImage(self.original_scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                orig_image.fill(Qt.white)
                painter = QPainter(orig_image)
                self.original_scene.render(painter)
                painter.end()
                orig_image.save(os.path.join(target_folder, f"orig_{filename}"))
                
                # 翻译图像
                trans_image = QImage(self.translated_scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                trans_image.fill(Qt.white)
                painter = QPainter(trans_image)
                self.translated_scene.render(painter)
                painter.end()
                trans_image.save(os.path.join(target_folder, filename))
            
            # 恢复当前索引
            self.current_index = current
            self.load_current_image_pair()
            
            QMessageBox.information(self, "导出完成", 
                f"已导出 {len(self.image_pairs)} 对图像。\n"
                f"需要修改: {len(self.modified_images)}\n"
                f"已通过: {len(self.image_pairs) - len(self.modified_images)}")
                
        except Exception as e:
            QMessageBox.warning(self, "导出错误", f"导出图像时出错: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageComparisonTool()
    window.show()
    sys.exit(app.exec_())