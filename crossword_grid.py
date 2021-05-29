import cv2
import numpy as np
import math
import os
import sys
from datetime import date, timedelta
import requests
import bangla
from PySide2.QtCore import QSize, QAbstractTableModel, Qt, QTimer
from PySide2.QtGui import QPixmap, QPalette, QColor, QFont, QBrush
from PySide2.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QVBoxLayout, QTableWidget, \
  QStyledItemDelegate, QTableView, QLabel, QHBoxLayout, QGridLayout, QToolBar, QDialogButtonBox, QStatusBar, QTextEdit, \
  QWidget, QMessageBox

url_format = 'https://epaper.anandabazar.com/epaperimages////{}////{}-md-hr-2ll.png'
app_title = 'শব্দছক'

grid_left = 30
grid_right = 512
grid_top = 202
grid_bottom = 701

right_clues_left = 516
right_clues_right = 760
right_clues_top = 190
right_clues_bottom = 524

down_clues_left = 24
down_clues_rigth = 516
down_clues_top = 705
down_clues_bottom = 808

grid_cell_size = 30
grid_row_count = 15
grid_column_count = 15

bg_left_border = 10
bg_ystart = 190
cv_white = [255, 255, 255]

icons_folder = 'icons'
font_name = 'Kalpurush'
font_size = 14

def convertYValToGridVal(y_val):
  y_max = 255
  y_min = 155
  y_min_max = y_min + (y_max - y_min) / 5 # max of y_min
  y_max_min = y_max - (y_max - y_min) / 5 # min of y_max
  return 0 if y_val < y_min_max else 1 if y_val > y_max_min else -1

def saveImageAndCluesFromWebsite(day):
  dateStr = day.strftime("%d%m%Y")
  crossword_index = (day - date(2021, 5, 28)).days + 7293
  if os.path.isfile('image-{}.png'.format(crossword_index)):
    return crossword_index;

  headers = requests.utils.default_headers()
  headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0'})

  img_url = url_format.format(dateStr, dateStr)
  response = requests.get(img_url, headers)
  with open('image-{}.png'.format(crossword_index), 'wb') as f:
    f.write(response.content)

  print('Crossword {} has been fetched from website'.format(crossword_index))
  return crossword_index

def convertImageToGrid(filename, grid):
  image_orig = cv2.imread(filename)
  image_cropped = image_orig[grid_top:grid_bottom, grid_left:grid_right]
  cv2.imwrite('image_cropped.png', image_cropped)
  image_gray = cv2.cvtColor(image_cropped, cv2.COLOR_BGR2GRAY)
  nrows, ncols = image_gray.shape

  shape = grid.shape
  for i in range(shape[0]):
    for j in range(shape[1]):
      xmin = math.ceil(ncols * j / shape[1])
      xmax = math.floor(ncols * (j + 1) / shape[1])
      ymin = math.ceil(nrows * i / shape[0])
      ymax = math.floor(nrows * (i + 1) / shape[0])
      cell = image_gray[ymin:ymax, xmin:xmax]

      pixels = np.float32(cell.reshape(-1))
      n_colors = 2
      criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, .1)
      flags = cv2.KMEANS_RANDOM_CENTERS

      _, labels, palette = cv2.kmeans(pixels, n_colors, None, criteria, 10, flags)
      _, counts = np.unique(labels, return_counts=True)
      dominant = palette[np.argmax(counts)]
      gridVal = convertYValToGridVal(dominant)
      assert(gridVal in [0, 1])
      grid[i][j][0] = gridVal

  clue_index = 0
  for i in range(shape[0]):
    for j in range(shape[1]):
      if not grid[i][j][0]:
        continue
      found_horizontal = False
      if (j == 0 or not grid[i][j - 1][0]) and j != shape[1] - 1 and grid[i][j + 1][0]:
        clue_index += 1
        grid[i][j][1] = clue_index
        found_horizontal = True
      if (i == 0 or not grid[i - 1][j][0]) and i != shape[0] - 1 and grid[i + 1][j][0]:
        if not found_horizontal:
          clue_index += 1
        grid[i][j][2] = clue_index
  return grid

def saveClueImages(filename):
  image_orig = cv2.imread(filename)
  image_down_clues = image_orig[down_clues_top:down_clues_bottom, down_clues_left:down_clues_rigth].copy()
  cv2.imwrite('down_clues.png', image_down_clues)
  image_right_clues = image_orig[right_clues_top:right_clues_bottom, right_clues_left:right_clues_right].copy()
  cv2.imwrite('right_clues.png', image_right_clues)

class CrosswordGridModel(QAbstractTableModel):
    def __init__(self, crossword_index, grid_data, parent=None):
      super(CrosswordGridModel, self).__init__(parent)
      self.crossword_index = crossword_index
      self.load_grid_data(grid_data)
      shape = grid_data.shape
      self.solution_data = np.full((shape[0], shape[1]), '', dtype=object)
      self.timer = QTimer(self)
      self.timer.timeout.connect(self.save_solution_auto)
      self.timer.start(5000)

    def clear_solution(self):
      self.solution_data.fill('')
      self.layoutChanged.emit()
      msgBox = QMessageBox(QMessageBox.Information, app_title, 'Progress cleared')
      msgBox.exec_()

    def save_solution_auto(self):
      if not np.any(self.solution_data):
        return False
      shape = self.solution_data.shape
      with open('solution-{}.txt'.format(self.crossword_index), 'wb') as f:
        for i in range(shape[0]):
          for j in range(shape[1]):
            f.write((self.solution_data[i][j] + '\n').encode('utf-8'))

    def save_solution(self):
      self.save_solution_auto()
      msgBox = QMessageBox(QMessageBox.Information, app_title, 'Progress saved')
      msgBox.exec_()

    def load_solution(self):
      shape = self.solution_data.shape
      msgBox = QMessageBox()
      msgBox.setIcon(QMessageBox.Information)
      msgBox.setWindowTitle(app_title)
      try:
        with open('solution-{}.txt'.format(self.crossword_index), encoding='utf-8', mode='r') as f:
          for i in range(shape[0]):
            for j in range(shape[1]):
              self.solution_data[i][j] = f.readline().strip()
        self.layoutChanged.emit()
        msgBox.setText('Solution loaded')
      except IOError:
        msgBox.setText('No saved solution!')
      msgBox.exec_()

    def load_grid_data(self, grid_data):
      self.grid_data = grid_data
      shape = grid_data.shape
      self.row_count = shape[0]
      self.column_count = shape[1]

    def rowCount(self, parent):
      return self.row_count

    def columnCount(self, parent):
      return self.column_count

    def headerData(self, section, orientation, role):
      return None

    def flags(self, index):
      row = index.row()
      column = index.column()
      is_word_cell = self.grid_data[row][column][0]
      if is_word_cell:
        return Qt.ItemIsEnabled | Qt.ItemIsEditable
      return Qt.ItemIsEnabled

    def data(self, index, role=Qt.DisplayRole):
      row = index.row()
      column = index.column()
      cell_data = self.grid_data[row][column]
      is_word_cell = cell_data[0]
      clue_index = cell_data[1] or cell_data[2]

      if role == Qt.DisplayRole:
        return self.solution_data[row][column]
      if role == Qt.EditRole:
        return self.solution_data[row][column]
      elif role == Qt.BackgroundRole:
        if is_word_cell:
          if clue_index:
            icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
            brush = QBrush()
            pixmap = QPixmap(icon_path)
            brush.setTexture(pixmap)
            return brush
          else:
            return QColor(Qt.white)
        else:
          return QColor(Qt.black)
      elif role == Qt.FontRole:
        font = QFont(font_name, font_size)
        return font
      elif role == Qt.TextAlignmentRole:
        return Qt.AlignCenter
      return None

    def setData(self, index, value, role=Qt.EditRole):
      row = index.row()
      column = index.column()
      if role == Qt.EditRole:
        self.solution_data[row][column] = value
        return True
      elif role == Qt.FontRole:
        font = QFont(font_name, font_size)
        return font
      elif role == Qt.TextAlignmentRole:
        return Qt.AlignCenter
      return False

class Form(QDialog):
  def __init__(self, crossword_index, grid_data, parent=None):
    super(Form, self).__init__(parent)
    self.setWindowTitle('{} {}    {}'.format(app_title, bangla.convert_english_digit_to_bangla_digit(crossword_index), date.today().strftime("%A, %d %B, %Y")))
    self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    tableModel = CrosswordGridModel(crossword_index, grid_data, self)
    tableView = QTableView(self)
    tableView.horizontalHeader().hide()
    tableView.verticalHeader().hide()
    tableView.setModel(tableModel)
    for i in range(grid_row_count):
      tableView.setRowHeight(i, grid_cell_size)
    for i in range(grid_column_count):
      tableView.setColumnWidth(i, grid_cell_size)
    print(tableView.rowHeight(10))
    print(tableView.columnWidth(10))

    right_label = QLabel(self)
    right_pixmap = QPixmap('right_clues.png')
    right_label.setPixmap(right_pixmap)

    down_label = QLabel(self)
    down_pixmap = QPixmap('down_clues.png')
    down_label.setPixmap(down_pixmap)

    saveButton = QPushButton('Save progress', self)
    loadButton = QPushButton('Load progress', self)
    clearButton = QPushButton('Clear progress', self)
    saveButton.clicked.connect(tableModel.save_solution)
    loadButton.clicked.connect(tableModel.load_solution)
    clearButton.clicked.connect(tableModel.clear_solution)
    bbox = QDialogButtonBox(self)
    bbox.addButton(saveButton, QDialogButtonBox.AcceptRole)
    bbox.addButton(loadButton, QDialogButtonBox.AcceptRole)
    bbox.addButton(clearButton, QDialogButtonBox.AcceptRole)

    layout = QGridLayout(self)
    layout.addWidget(tableView, 0, 0)
    layout.addWidget(right_label, 0, 1, Qt.AlignLeft | Qt.AlignTop)
    layout.addWidget(down_label, 1, 0, Qt.AlignLeft | Qt.AlignTop)
    layout.addWidget(bbox, 1, 1, Qt.AlignHCenter | Qt.AlignBottom)
    self.setLayout(layout)

    windowWidth = tableView.columnWidth(0) * grid_column_count + grid_column_count - 1 + right_clues_right - right_clues_left + layout.horizontalSpacing() + 27
    windowHeight = tableView.rowHeight(0) * grid_row_count + grid_row_count - 1 + down_clues_bottom - down_clues_top + layout.verticalSpacing() + 10
    self.setFixedSize(QSize(windowWidth, windowHeight))

if __name__ == '__main__':
  crossword_index = saveImageAndCluesFromWebsite(date.today())
  grid = np.zeros((grid_column_count, grid_row_count, 3), dtype=int)
  imgFile = 'image-{}.png'.format(crossword_index)
  convertImageToGrid(imgFile, grid)
  saveClueImages(imgFile)

  app = QApplication(sys.argv)
  form = Form(crossword_index, grid)
  form.show()
  sys.exit(app.exec_())