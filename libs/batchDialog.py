from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QSpinBox, QComboBox, QPushButton, QCheckBox,
                            QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal

class BatchDialog(QDialog):
    # 添加信号用于实时预览
    paramsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None, label_list=None, canvas_size=None):
        super(BatchDialog, self).__init__(parent)
        self.parent = parent
        self.label_list = label_list if label_list else []
        print(f"Received labels: {self.label_list}")  # 调试输出
        self.canvas_size = canvas_size or (800, 600)
        
        self.setWindowTitle('批量创建标注')
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 标签选择
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel('标注类型:'))
        self.label_combo = QComboBox()
        
        # 确保标签列表不为空并正确添加到下拉框
        if self.label_list:
            self.label_combo.addItems(self.label_list)
            self.label_combo.setCurrentIndex(0)  # 设置默认选中第一项
        print(f"Added {len(self.label_list)} labels to combo box")  # 调试输出
        
        label_layout.addWidget(self.label_combo)
        layout.addLayout(label_layout)
        
        # 位置设置组
        position_group = QGroupBox("位置设置")
        position_layout = QHBoxLayout()
        
        position_layout.addWidget(QLabel('左上角 X:'))
        self.start_x_spin = QSpinBox()
        self.start_x_spin.setRange(0, self.canvas_size[0])
        self.start_x_spin.setValue(0)
        position_layout.addWidget(self.start_x_spin)
        
        position_layout.addWidget(QLabel('左上角 Y:'))
        self.start_y_spin = QSpinBox()
        self.start_y_spin.setRange(0, self.canvas_size[1])
        self.start_y_spin.setValue(0)
        position_layout.addWidget(self.start_y_spin)
        
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        # 网格设置组
        grid_group = QGroupBox("网格设置")
        grid_layout = QHBoxLayout()
        
        grid_layout.addWidget(QLabel('行数:'))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 100)
        self.rows_spin.setValue(3)
        grid_layout.addWidget(self.rows_spin)
        
        grid_layout.addWidget(QLabel('列数:'))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 100)
        self.cols_spin.setValue(3)
        grid_layout.addWidget(self.cols_spin)
        
        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)
        
        # 间距设置组
        spacing_group = QGroupBox("间距设置")
        spacing_layout = QHBoxLayout()
        
        spacing_layout.addWidget(QLabel('水平间距:'))
        self.h_spacing_spin = QSpinBox()
        self.h_spacing_spin.setRange(0, 1000)
        self.h_spacing_spin.setValue(16)
        spacing_layout.addWidget(self.h_spacing_spin)
        
        spacing_layout.addWidget(QLabel('垂直间距:'))
        self.v_spacing_spin = QSpinBox()
        self.v_spacing_spin.setRange(0, 1000)
        self.v_spacing_spin.setValue(15)
        spacing_layout.addWidget(self.v_spacing_spin)
        
        spacing_group.setLayout(spacing_layout)
        layout.addWidget(spacing_group)
        
        # 大小设置组
        size_group = QGroupBox("大小设置")
        size_layout = QHBoxLayout()
        
        size_layout.addWidget(QLabel('宽度:'))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 1000)
        self.width_spin.setValue(20)
        size_layout.addWidget(self.width_spin)
        
        size_layout.addWidget(QLabel('高度:'))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 1000)
        self.height_spin.setValue(15)
        size_layout.addWidget(self.height_spin)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # 预览选项
        preview_layout = QHBoxLayout()
        self.preview_checkbox = QCheckBox('实时预览')
        self.preview_checkbox.setChecked(True)
        preview_layout.addWidget(self.preview_checkbox)
        layout.addLayout(preview_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def setup_connections(self):
        """设置信号连接"""
        # 所有可能改变参数的控件都连接到update_preview
        spinboxes = [
            self.start_x_spin, self.start_y_spin,
            self.rows_spin, self.cols_spin,
            self.h_spacing_spin, self.v_spacing_spin,
            self.width_spin, self.height_spin
        ]
        
        for spinbox in spinboxes:
            spinbox.valueChanged.connect(self.update_preview)
            
        self.label_combo.currentTextChanged.connect(self.update_preview)
        self.preview_checkbox.stateChanged.connect(self.update_preview)
    
    def update_preview(self):
        """更新预览"""
        if self.preview_checkbox.isChecked():
            self.paramsChanged.emit(self.get_params())
    
    def get_params(self):
        """获取所有参数"""
        return {
            'label': self.label_combo.currentText(),
            'start_x': self.start_x_spin.value(),
            'start_y': self.start_y_spin.value(),
            'rows': self.rows_spin.value(),
            'cols': self.cols_spin.value(),
            'h_spacing': self.h_spacing_spin.value(),
            'v_spacing': self.v_spacing_spin.value(),
            'width': self.width_spin.value(),
            'height': self.height_spin.value()
        } 