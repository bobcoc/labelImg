try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

# from PyQt4.QtOpenGL import *

from libs.shape import Shape
from libs.utils import distance
from PyQt5.QtCore import pyqtSignal
CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor

# class Canvas(QGLWidget):


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    lightRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)
    shape_selection_changed = pyqtSignal(bool)

    CREATE, EDIT = list(range(2))

    epsilon = 24.0

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selected_shape = None  # save the selected shape here
        self.selected_shape_copy = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        self.line = Shape(line_color=self.drawing_line_color)
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.overlay_color = None
        self.label_font_size = 8
        self.pixmap = QPixmap()
        self.visible = {}
        self._hide_background = False
        self.hide_background = False
        self.h_shape = None
        self.h_vertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.verified = False
        self.draw_square = False

        # initialisation for panning
        self.pan_initial_pos = QPoint()

        self.preview_shapes = []  # 添加预览形状列表

        # 添加多选相关的属性
        self.selected_shapes = []  # 存储多个选中的shape
        self.is_ctrl_pressed = False  # 控制键状态
        self.selection_box = None  # 框选区域
        self.selection_box_start = None  # 框选起始点

    def set_drawing_color(self, qcolor):
        self.drawing_line_color = qcolor
        self.drawing_rect_color = qcolor

    def enterEvent(self, ev):
        self.override_cursor(self._cursor)

    def leaveEvent(self, ev):
        self.restore_cursor()

    def focusOutEvent(self, ev):
        self.restore_cursor()

    def isVisible(self, shape):
        return hasattr(shape, 'visible') and shape.visible

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def set_editing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.un_highlight()
            self.deselect_shape()
        self.prev_point = QPointF()
        self.repaint()

    def un_highlight(self, shape=None):
        if shape == None or shape == self.h_shape:
            if self.h_shape:
                self.h_shape.highlight_clear()
            self.h_vertex = self.h_shape = None

    def selected_vertex(self):
        return self.h_vertex is not None

    def mouseMoveEvent(self, ev):
        pos = self.transform_pos(ev.pos())

        # Update coordinates in status bar if image is opened
        window = self.parent().window()
        if window.file_path is not None:
            self.parent().window().label_coordinates.setText(
                'X: %d; Y: %d' % (pos.x(), pos.y()))

        # 如果是框选模式
        if ev.buttons() & Qt.LeftButton and self.is_ctrl_pressed:
            # 更新框选区域
            if self.selection_box_start:
                self.selection_box = QRectF(
                    self.selection_box_start,
                    pos
                ).normalized()
                self.update()
                return

        # Polygon drawing.
        if self.drawing():
            self.override_cursor(CURSOR_DRAW)
            if self.current:
                # Display annotation width and height while drawing
                current_width = abs(self.current[0].x() - pos.x())
                current_height = abs(self.current[0].y() - pos.y())
                self.parent().window().label_coordinates.setText(
                        'Width: %d, Height: %d / X: %d; Y: %d' % (current_width, current_height, pos.x(), pos.y()))

                color = self.drawing_line_color
                if self.out_of_pixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Clip the coordinates to 0 or max,
                    # if they are outside the range [0, max]
                    size = self.pixmap.size()
                    clipped_x = min(max(0, pos.x()), size.width())
                    clipped_y = min(max(0, pos.y()), size.height())
                    pos = QPointF(clipped_x, clipped_y)
                elif len(self.current) > 1 and self.close_enough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:
                    pos = self.current[0]
                    color = self.current.line_color
                    self.override_cursor(CURSOR_POINT)
                    self.current.highlight_vertex(0, Shape.NEAR_VERTEX)

                if self.draw_square:
                    init_pos = self.current[0]
                    min_x = init_pos.x()
                    min_y = init_pos.y()
                    min_size = min(abs(pos.x() - min_x), abs(pos.y() - min_y))
                    direction_x = -1 if pos.x() - min_x < 0 else 1
                    direction_y = -1 if pos.y() - min_y < 0 else 1
                    self.line[1] = QPointF(min_x + direction_x * min_size, min_y + direction_y * min_size)
                else:
                    self.line[1] = pos

                self.line.line_color = color
                self.prev_point = QPointF()
                self.current.highlight_clear()
            else:
                self.prev_point = pos
            self.repaint()
            return

        # Polygon copy moving.
        if Qt.RightButton & ev.buttons():
            if self.selected_shape_copy and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape_copy, pos)
                self.repaint()
            elif self.selected_shape:
                self.selected_shape_copy = self.selected_shape.copy()
                self.repaint()
            return

        # Polygon/Vertex moving.
        if Qt.LeftButton & ev.buttons():
            if self.selected_vertex():
                self.bounded_move_vertex(pos)
                self.shapeMoved.emit()
                self.repaint()
            elif self.selected_shape and self.prev_point:
                # 移动所有选中的shapes
                if self.selected_shapes:
                    for shape in self.selected_shapes:
                        self.bounded_move_shape(shape, pos)
                else:
                    self.bounded_move_shape(self.selected_shape, pos)
                self.shapeMoved.emit()
                self.repaint()
            else:
                # pan
                delta = ev.pos() - self.pan_initial_pos
                self.scrollRequest.emit(delta.x(), Qt.Horizontal)
                self.scrollRequest.emit(delta.y(), Qt.Vertical)
                self.update()
            return

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip("Image")
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearest_vertex(pos, self.epsilon)
            if index is not None:
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = index, shape
                shape.highlight_vertex(index, shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setToolTip("Click & drag to move point")
                self.setStatusTip(self.toolTip())
                self.update()
                break
            elif shape.contains_point(pos):
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = None, shape
                self.setToolTip(
                    "Click & drag to move shape '%s'" % shape.label)
                self.setStatusTip(self.toolTip())
                self.override_cursor(CURSOR_GRAB)
                self.update()
                break
        else:
            if self.h_shape:
                self.h_shape.highlight_clear()
                self.update()
            self.h_vertex, self.h_shape = None, None
            self.override_cursor(CURSOR_DEFAULT)

    def mousePressEvent(self, ev):
        pos = self.transform_pos(ev.pos())

        if ev.button() == Qt.LeftButton:
            if self.drawing():
                if not self.current:  # 只在开始画的时候记录起始点
                    self.handle_drawing(pos)
            else:
                # 传入是否是多选模式的标志
                multiple_selection_mode = bool(ev.modifiers() & Qt.ControlModifier)
                selection = self.select_shape_point(pos, multiple_selection_mode)
                self.prev_point = pos

                if selection is not None:
                    if ev.modifiers() == Qt.ControlModifier:
                        # Ctrl+单击时的多选逻辑
                        if isinstance(selection, Shape):  # 如果返回的是shape对象
                            if selection in self.selected_shapes:
                                # 如果shape已被选中，从选中列表中移除
                                self.selected_shapes.remove(selection)
                                selection.selected = False
                                if selection == self.selected_shape:
                                    self.selected_shape = None
                                # 发送选择改变信号
                                self.selectionChanged.emit(bool(self.selected_shapes))
                                self.shape_selection_changed.emit(bool(self.selected_shapes))
                    else:
                        # 普通单击，已经在select_shape_point中处理了选择
                        self.calculate_offsets(self.selected_shape, pos)
                else:
                    # 点击空白区域
                    if ev.modifiers() == Qt.ControlModifier:
                        # Ctrl+空白区域开始框选
                        self.selection_box_start = pos
                        self.selection_box = QRectF(pos, pos)
                    else:
                        # 普通点击空白区域，取消所有选择并准备平移
                        self.deselect_shape()
                        QApplication.setOverrideCursor(QCursor(Qt.OpenHandCursor))
                        self.pan_initial_pos = ev.pos()

        elif ev.button() == Qt.RightButton and self.editing():
            self.select_shape_point(pos)
            self.prev_point = pos
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.RightButton:
            menu = self.menus[bool(self.selected_shape_copy)]
            self.restore_cursor()
            if not menu.exec_(self.mapToGlobal(ev.pos()))\
               and self.selected_shape_copy:
                # Cancel the move by deleting the shadow copy.
                self.selected_shape_copy = None
                self.repaint()
        elif ev.button() == Qt.LeftButton and self.is_ctrl_pressed:
            # 完成框选,选中框内的shapes
            if self.selection_box:
                # 清除之前的选择
                for shape in self.selected_shapes:
                    shape.selected = False
                self.selected_shapes.clear()
                
                # 选中框内的可见shapes
                for shape in self.shapes:
                    # 使用isVisible方法检查shape是否可见且在选择框内
                    if self.isVisible(shape) and self.is_shape_in_box(shape, self.selection_box):
                        self.selected_shapes.append(shape)
                        shape.selected = True
                        # 如果是第一个选中的shape，设置为主选中shape
                        if not self.selected_shape:
                            self.selected_shape = shape
                
                # 清除选择框
                self.selection_box = None
                self.selection_box_start = None
                self.update()
                # 发送选择改变信号
                self.selectionChanged.emit(bool(self.selected_shapes))
                return
        elif ev.button() == Qt.LeftButton:
            if self.drawing():
                if self.current:
                    # 在鼠标释放时完成矩形绘制
                    pos = self.transform_pos(ev.pos())
                    if self.out_of_pixmap(pos):
                        # 如果超出边界，调整到边界位置
                        size = self.pixmap.size()
                        pos = QPointF(
                            min(max(0, pos.x()), size.width()),
                            min(max(0, pos.y()), size.height())
                        )
                    # 确保添加四个点来形成矩形
                    init_pos = self.current[0]
                    self.current.points = []  # 清空现有点
                    self.current.add_point(init_pos)
                    self.current.add_point(QPointF(pos.x(), init_pos.y()))
                    self.current.add_point(pos)
                    self.current.add_point(QPointF(init_pos.x(), pos.y()))
                    self.current.close()  # 关闭形状
                    self.finalise()
                    self.line.points = []  # 清空临时线
                elif self.selected_vertex():
                    self.override_cursor(CURSOR_POINT)
                else:
                    self.override_cursor(CURSOR_GRAB)
            # pan
            QApplication.restoreOverrideCursor()

    def end_move(self, copy=False):
        assert self.selected_shape and self.selected_shape_copy
        shape = self.selected_shape_copy
        # del shape.fill_color
        # del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selected_shape.selected = False
            self.selected_shape = shape
            self.repaint()
        else:
            self.selected_shape.points = [p for p in shape.points]
        self.selected_shape_copy = None

    def hide_background_shapes(self, value):
        self.hide_background = value
        if self.selected_shape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            for shape in self.shapes:
                if shape != self.selected_shape:
                    shape.visible = not value
            self.repaint()

    def set_hiding(self, enable=True):
        self._hide_background = self.hide_background if enable else False
        if self._hide_background:
            for shape in self.shapes:
                if shape != self.selected_shape:
                    shape.visible = False
        else:
            for shape in self.shapes:
                shape.visible = True
        self.repaint()

    def handle_drawing(self, pos):
        if not self.out_of_pixmap(pos):
            self.current = Shape()
            self.current.add_point(pos)
            self.line.points = [pos, pos]
            self.set_hiding()
            self.drawingPolygon.emit(True)
            self.update()

    def can_close_shape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.can_close_shape() and len(self.current) > 3:
            self.current.pop_point()
            self.finalise()

    def select_shape(self, shape):
        """选中单个shape"""
        if not self.is_ctrl_pressed:
            # 如果没有按住Ctrl，清除之前的选择
            self.deselect_shape()
        shape.selected = True
        if shape not in self.selected_shapes:
            self.selected_shapes.append(shape)
        self.selected_shape = shape
        # 发送两个选择改变的信号
        self.selectionChanged.emit(True)  # 原有的信号
        self.shape_selection_changed.emit(True)  # 新增的信号
        self.update()

    def select_shape_point(self, point, multiple_selection_mode=False):
        """Select the first shape created which contains this point."""
        if not multiple_selection_mode:
            self.deselect_shape()
        
        if self.selected_vertex():  # A vertex is marked for selection.
            index, shape = self.h_vertex, self.h_shape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)
            self.select_shape(shape)
            return self.h_vertex
        
        for shape in reversed(self.shapes):
            if self.isVisible(shape) and shape.contains_point(point):
                self.select_shape(shape)
                self.calculate_offsets(shape, point)
                return shape
        return None

    def calculate_offsets(self, shape, point):
        rect = shape.bounding_rect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def snap_point_to_canvas(self, x, y):
        """
        Moves a point x,y to within the boundaries of the canvas.
        :return: (x,y,snapped) where snapped is True if x or y were changed, False if not.
        """
        if x < 0 or x > self.pixmap.width() or y < 0 or y > self.pixmap.height():
            x = max(x, 0)
            y = max(y, 0)
            x = min(x, self.pixmap.width())
            y = min(y, self.pixmap.height())
            return x, y, True

        return x, y, False

    def bounded_move_vertex(self, pos):
        index, shape = self.h_vertex, self.h_shape
        point = shape[index]
        if self.out_of_pixmap(pos):
            size = self.pixmap.size()
            clipped_x = min(max(0, pos.x()), size.width())
            clipped_y = min(max(0, pos.y()), size.height())
            pos = QPointF(clipped_x, clipped_y)

        if self.draw_square:
            opposite_point_index = (index + 2) % 4
            opposite_point = shape[opposite_point_index]

            min_size = min(abs(pos.x() - opposite_point.x()), abs(pos.y() - opposite_point.y()))
            direction_x = -1 if pos.x() - opposite_point.x() < 0 else 1
            direction_y = -1 if pos.y() - opposite_point.y() < 0 else 1
            shift_pos = QPointF(opposite_point.x() + direction_x * min_size - point.x(),
                                opposite_point.y() + direction_y * min_size - point.y())
        else:
            shift_pos = pos - point

        shape.move_vertex_by(index, shift_pos)

        left_index = (index + 1) % 4
        right_index = (index + 3) % 4
        left_shift = None
        right_shift = None
        if index % 2 == 0:
            right_shift = QPointF(shift_pos.x(), 0)
            left_shift = QPointF(0, shift_pos.y())
        else:
            left_shift = QPointF(shift_pos.x(), 0)
            right_shift = QPointF(0, shift_pos.y())
        shape.move_vertex_by(right_index, right_shift)
        shape.move_vertex_by(left_index, left_shift)

    def bounded_move_shape(self, shape, pos):
        if self.out_of_pixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.out_of_pixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.out_of_pixmap(o2):
            pos += QPointF(min(0, self.pixmap.width() - o2.x()),
                           min(0, self.pixmap.height() - o2.y()))
        dp = pos - self.prev_point
        if dp:
            shape.move_by(dp)
            self.prev_point = pos
            return True
        return False

    def deselect_shape(self):
        """取消所有选中状态"""
        if self.selected_shape:
            self.selected_shape.selected = False
            self.selected_shape = None
        for shape in self.selected_shapes:
            shape.selected = False
        self.selected_shapes.clear()
        # 发送两个选择改变信号
        self.selectionChanged.emit(False)
        self.shape_selection_changed.emit(False)
        self.update()

    def delete_selected(self):
        """删除所有选中的shapes"""
        deleted = []
        if self.selected_shapes:
            for shape in self.selected_shapes:
                if shape in self.shapes:
                    self.shapes.remove(shape)
                    deleted.append(shape)
            self.selected_shapes.clear()
            self.selected_shape = None
            self.update()
        elif self.selected_shape:
            shape = self.selected_shape
            if shape in self.shapes:
                self.shapes.remove(shape)
                self.selected_shape = None
                deleted.append(shape)
                self.update()
        return deleted[0] if len(deleted) == 1 else deleted  # 如果只删除一个，返回单个shape，否则返回列表

    def copy_selected_shape(self):
        if self.selected_shape:
            shape = self.selected_shape.copy()
            self.deselect_shape()
            self.shapes.append(shape)
            shape.selected = True
            self.selected_shape = shape
            self.bounded_shift_shape(shape)
            return shape

    def bounded_shift_shape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculate_offsets(shape, point)
        self.prev_point = point
        if not self.bounded_move_shape(shape, point - offset):
            self.bounded_move_shape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.HighQualityAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offset_to_center())

        temp = self.pixmap
        if self.overlay_color:
            temp = QPixmap(self.pixmap)
            painter = QPainter(temp)
            painter.setCompositionMode(painter.CompositionMode_Overlay)
            painter.fillRect(temp.rect(), self.overlay_color)
            painter.end()

        p.drawPixmap(0, 0, temp)
        Shape.scale = self.scale
        Shape.label_font_size = self.label_font_size

        # 先绘制所有未选中的shapes
        for shape in self.shapes:
            if not self.isVisible(shape):  # 跳过不可见的形状
                continue
            if (shape.selected or not self._hide_background):
                if shape not in self.selected_shapes:  # 只绘制未选中的
                    shape.fill = shape.selected or shape == self.h_shape
                    shape.paint(p)

        # 再绘制选中的shapes，确保它们在最上层
        for shape in self.selected_shapes:
            if self.isVisible(shape):  # 只绘制可见的形状
                shape.fill = True  # 选中的shape填充显示
                shape.paint(p)

        # 绘制当前正在创建的shape
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selected_shape_copy:
            self.selected_shape_copy.paint(p)

        # 绘制选择框
        if self.selection_box:
            p.setPen(QPen(QColor(0, 120, 255), 1, Qt.SolidLine))
            p.setBrush(QColor(0, 120, 255, 30))
            p.drawRect(self.selection_box)

        # 绘制预览形状
        for shape in self.preview_shapes:
            shape.paint(p)

        p.end()

    def transform_pos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offset_to_center()

    def offset_to_center(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def out_of_pixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self):
        assert self.current
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return

        # 在关闭形状之前进行自动收缩
        if self.pixmap:
            # 获取当前矩形的边界
            rect = self.current.bounding_rect()
            x1, y1, x2, y2 = int(rect.x()), int(rect.y()), int(rect.x() + rect.width()), int(rect.y() + rect.height())
            
            # 确保边界在图片范围内
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(self.pixmap.width(), x2)
            y2 = min(self.pixmap.height(), y2)
            
            # 将QPixmap转换为QImage以进行像素分析
            image = self.pixmap.toImage()
            
            def is_content_pixel(x, y):
                # 获取像素颜色
                color = QColor(image.pixel(x, y))
                # 计算灰度值
                gray_value = (color.red() + color.green() + color.blue()) / 3
                # 使用更严格的阈值
                return gray_value < 150
            
            # 定义边距
            MARGIN = 0  # 边距像素
            
            # 左边界 - 从左向右扫描
            for x in range(x1, x2):
                has_content = False
                for y in range(y1, y2):
                    if is_content_pixel(x, y):
                        x1 = max(x - MARGIN, 0)
                        has_content = True
                        break
                if has_content:
                    break
            
            # 右边界 - 从右向左扫描
            for x in range(x2 - 1, x1, -1):
                has_content = False
                for y in range(y1, y2):
                    if is_content_pixel(x, y):
                        x2 = min(x + MARGIN, self.pixmap.width())
                        has_content = True
                        break
                if has_content:
                    break
            
            # 上边界 - 从上向下扫描
            for y in range(y1, y2):
                has_content = False
                for x in range(x1, x2):
                    if is_content_pixel(x, y):
                        y1 = max(y - MARGIN, 0)
                        has_content = True
                        break
                if has_content:
                    break
            
            # 下边界 - 从下向上扫描
            for y in range(y2 - 1, y1, -1):
                has_content = False
                for x in range(x1, x2):
                    if is_content_pixel(x, y):
                        y2 = min(y + MARGIN, self.pixmap.height())
                        has_content = True
                        break
                if has_content:
                    break

            # 确保最小尺寸
            MIN_SIZE = 5  # 最小尺寸（像素）
            if x2 - x1 < MIN_SIZE:
                center = (x1 + x2) / 2
                x1 = max(0, center - MIN_SIZE / 2)
                x2 = min(self.pixmap.width(), center + MIN_SIZE / 2)
            if y2 - y1 < MIN_SIZE:
                center = (y1 + y2) / 2
                y1 = max(0, center - MIN_SIZE / 2)
                y2 = min(self.pixmap.height(), center + MIN_SIZE / 2)
            
            # 更新形状的点
            self.current.points = [
                QPointF(x1, y1),
                QPointF(x2, y1),
                QPointF(x2, y2),
                QPointF(x1, y2)
            ]

        self.current.close()
        self.shapes.append(self.current)
        self.current = None
        self.set_hiding(False)
        self.newShape.emit()
        self.update()

    def close_enough(self, p1, p2):
        # d = distance(p1 - p2)
        # m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        qt_version = 4 if hasattr(ev, "delta") else 5
        if qt_version == 4:
            if ev.orientation() == Qt.Vertical:
                v_delta = ev.delta()
                h_delta = 0
            else:
                h_delta = ev.delta()
                v_delta = 0
        else:
            delta = ev.angleDelta()
            h_delta = delta.x()
            v_delta = delta.y()

        mods = ev.modifiers()
        if int(Qt.ControlModifier) | int(Qt.ShiftModifier) == int(mods) and v_delta:
            self.lightRequest.emit(v_delta)
        elif Qt.ControlModifier == int(mods) and v_delta:
            self.zoomRequest.emit(v_delta)
        else:
            v_delta and self.scrollRequest.emit(v_delta, Qt.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Return and self.can_close_shape():
            self.finalise()
        elif key == Qt.Key_Left and self.selected_shape:
            self.move_one_pixel('Left')
        elif key == Qt.Key_Right and self.selected_shape:
            self.move_one_pixel('Right')
        elif key == Qt.Key_Up and self.selected_shape:
            self.move_one_pixel('Up')
        elif key == Qt.Key_Down and self.selected_shape:
            self.move_one_pixel('Down')
        elif ev.key() == Qt.Key_Control:
            self.is_ctrl_pressed = True

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Control:
            self.is_ctrl_pressed = False

    def move_one_pixel(self, direction):
        """移动选中的shape(s)一个像素"""
        # 获取要移动的shapes列表
        shapes_to_move = self.selected_shapes if self.selected_shapes else [self.selected_shape] if self.selected_shape else []
        
        if not shapes_to_move:
            return
        
        # 根据方向确定移动的偏移量
        if direction == 'Left' and not self.move_out_of_bound(QPointF(-1.0, 0)):
            offset = QPointF(-1.0, 0)
        elif direction == 'Right' and not self.move_out_of_bound(QPointF(1.0, 0)):
            offset = QPointF(1.0, 0)
        elif direction == 'Up' and not self.move_out_of_bound(QPointF(0, -1.0)):
            offset = QPointF(0, -1.0)
        elif direction == 'Down' and not self.move_out_of_bound(QPointF(0, 1.0)):
            offset = QPointF(0, 1.0)
        else:
            return
        
        # 移动所有选中的shapes
        for shape in shapes_to_move:
            for point in shape.points:
                point += offset
                
        self.shapeMoved.emit()
        self.repaint()

    def move_out_of_bound(self, step):
        """检查移动是否会超出边界"""
        # 检查所有选中的shapes
        shapes_to_check = self.selected_shapes if self.selected_shapes else [self.selected_shape] if self.selected_shape else []
        
        for shape in shapes_to_check:
            points = [p1 + step for p1 in shape.points]
            if True in map(self.out_of_pixmap, points):
                return True
        return False

    def set_last_label(self, text, line_color=None, fill_color=None):
        self.shapes[-1].label = text
        if line_color:
            self.shapes[-1].line_color = line_color

        if fill_color:
            self.shapes[-1].fill_color = fill_color

        return self.shapes[-1]

    def undo_last_line(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def reset_all_lines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.shapes = []
        self.repaint()

    def load_shapes(self, shapes):
        self.shapes = list(shapes)
        self.current = None
        # 确保所有形状都有可见性属性
        for shape in self.shapes:
            if not hasattr(shape, 'visible'):
                shape.visible = True
        self.repaint()

    def set_shape_visible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def current_cursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def override_cursor(self, cursor):
        self._cursor = cursor
        if self.current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        QApplication.restoreOverrideCursor()

    def reset_state(self):
        self.deselect_shape()
        self.un_highlight()
        self.selected_shape_copy = None

        self.restore_cursor()
        self.pixmap = None
        self.update()

    def set_drawing_shape_to_square(self, status):
        self.draw_square = status

    def is_shape_in_box(self, shape, box):
        """判断shape是否在选择框内"""
        # 转换为画布坐标系下的矩形
        box_rect = box.normalized()
        # 检查shape的所有点是否在选择框内
        return any(box_rect.contains(point) for point in shape.points)

    def move_selected_shapes(self, dx, dy):
        """移动所有选中的shapes"""
        if self.selected_shapes:
            for shape in self.selected_shapes:
                for point in shape.points:
                    point.setX(point.x() + dx)
                    point.setY(point.y() + dy)
            self.update()
