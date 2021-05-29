import cv2
import numpy as np
import math

from PySide2.QtSvg import QSvgRenderer
from bs4 import BeautifulSoup
import requests
import bangla
import crossword
import ipuz
import sys
from PySide2.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, QSize, QRect
from PySide2.QtGui import QColor, QPixmap, QPainter, QFont, QIcon, QBrush, QPalette
from PySide2.QtWidgets import QHBoxLayout, QVBoxLayout, QHeaderView, QSizePolicy, QTableView, QWidget, QMainWindow, \
  QApplication, QPushButton, QAbstractItemDelegate, QStyledItemDelegate, QGridLayout
import os
from datetime import date, timedelta

url_format = 'https://epaper.anandabazar.com/epaperimages////{}////{}-md-hr-2ll.png'
grid_xstart = 30
grid_xend = 512
grid_ystart = 202
grid_yend = 701
grid_cell_size = 30

def convertYValToGridVal(y_val):
  y_max = 255
  y_min = 155
  y_min_max = y_min + (y_max - y_min) / 5 # max of y_min
  y_max_min = y_max - (y_max - y_min) / 5 # min of y_max
  return 0 if y_val < y_min_max else 1 if y_val > y_max_min else -1

english_digit_by_bangla_digit = {k : v for k, v in zip(bangla.bangla_number, bangla.english_number)}
def convertBanglaDigitsToEnglishDigits(number):
  for b, e in english_digit_by_bangla_digit.items():
    number = number.replace(b, e)
  return number

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
  image_cropped = image_orig[grid_ystart:grid_yend, grid_xstart:grid_xend]
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

status_bar = None
icons_folder = 'icons'
font_name ='Kalpurush'
font_size = 14
class CrosswordGridModel(QAbstractTableModel):
  def __init__(self, crossword_index=-1, grid_data=None):
    QAbstractTableModel.__init__(self)
    self.crossword_index = crossword_index
    self.load_grid_data(grid_data)
    shape = grid_data.shape
    self.solution_data = np.full((shape[0], shape[1]), '', dtype=object)
    self.timer = QTimer(self)
    self.timer.timeout.connect(self.save_solution)
    self.timer.start(5000)

  def clear_solution(self):
    self.solution_data.fill('')
    self.layoutChanged.emit()
    status_bar.showMessage("Solution cleared")

  def save_solution_auto(self):
    if not np.any(self.solution_data):
      return False
    shape = self.solution_data.shape
    with open('solution-{}.txt'.format(self.crossword_index), 'wb') as f:
      for i in range(shape[0]):
        for j in range(shape[1]):
          f.write((self.solution_data[i][j] + '\n').encode('utf-8'))
    return True

  def load_solution(self):
    shape = self.solution_data.shape
    try:
      with open('solution-{}.txt'.format(self.crossword_index), encoding='utf-8', mode='r') as f:
        for i in range(shape[0]):
          for j in range(shape[1]):
            self.solution_data[i][j] = f.readline().strip()
      self.layoutChanged.emit()
      status_bar.showMessage("Solution loaded")
    except IOError:
      status_bar.showMessage("No saved solution")

  def load_grid_data(self, grid_data):
    self.grid_data = grid_data
    shape = grid_data.shape
    self.row_count = shape[0]
    self.column_count = shape[1]

  def rowCount(self, parent=QModelIndex()):
    return self.row_count

  def columnCount(self, parent=QModelIndex()):
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
    #elif role == Qt.DecorationRole:
    #  if clue_index:
    #    icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
    #    return QIcon(icon_path)
    #  else:
    #    return None
    elif role == Qt.BackgroundRole:
      if is_word_cell:
        if clue_index:
          icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
          renderer = QSvgRenderer(icon_path)
          pixmap = QPixmap(QSize(grid_cell_size, grid_cell_size))
          pixmap.fill(Qt.transparent)
          painter = QPainter()
          renderer.render(painter, pixmap.rect())
          brush = QBrush()
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
      if status_bar:
        status_bar.clearMessage()
      return True
    elif role == Qt.FontRole:
      font = QFont(font_name, font_size)
      return font
    elif role == Qt.TextAlignmentRole:
      return Qt.AlignCenter
    return False

class CrosswordGridDelegate(QStyledItemDelegate):
  def __init__(self, grid_data):
    QStyledItemDelegate.__init__(self)
    self.grid_data = grid_data

  def paint(self, painter, option, index):
    row = index.row()
    column = index.column()
    cell_data = self.grid_data[row][column]
    is_word_cell = cell_data[0]
    clue_index = cell_data[1] or cell_data[2]

    painter.save()
    if is_word_cell:
      if clue_index:
        icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
        renderer = QSvgRenderer(icon_path)
        #pixmap = QPixmap(QSize(grid_cell_size, grid_cell_size))
        #pixmap.fill(Qt.transparent)
        renderer.render(painter, option.rect())
    painter.restore()

  def sizeHint(self, option, index):
    return QSize(grid_cell_size - 1, grid_cell_size - 1)

class CrosswordWidget(QWidget):
  def __init__(self, crossword_index, grid_data, grid_cell_length):
    QWidget.__init__(self)
    self.grid_model = CrosswordGridModel(crossword_index, grid_data)
    self.grid_delegate = CrosswordGridDelegate(grid_data)
    self.grid_table_view = QTableView(self)
    #sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    #self.grid_table_view.setSizePolicy(sizePolicy)
    self.grid_table_view.setModel(self.grid_model)
    self.grid_table_view.setItemDelegate(self.grid_delegate)
    self.grid_table_view.resizeColumnsToContents()
    self.grid_table_view.setStyleSheet("background:transparent")
    #self.grid_horizontal_header = self.grid_table_view.horizontalHeader()
    #self.grid_horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
    #self.grid_horizontal_header.setDefaultSectionSize(grid_cell_length)
    #self.grid_horizontal_header.hide()
    #self.grid_vertical_header = self.grid_table_view.verticalHeader()
    #self.grid_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
    #self.grid_vertical_header.setDefaultSectionSize(grid_cell_length * 1.3)
    #self.grid_vertical_header.hide()

    #self.main_layout = QHBoxLayout(self)
    #self.main_layout.addWidget(self.grid_table_view)
    #self.setLayout(self.main_layout)
    #self.layout().addWidget(self.grid_table_view)

  def save_solution(self):
    if self.grid_model.save_solution():
      status_bar.showMessage("Solution saved")

class CrosswordGridWindow(QMainWindow):
  def __init__(self, crossword_index, widget, window_width, window_height):
    QMainWindow.__init__(self)
    date_ = date.today().strftime("%A, %d %B, %Y")
    self.setWindowTitle('শব্দছক ' + bangla.convert_english_digit_to_bangla_digit(crossword_index) + '   ' + date_)
    layout = QGridLayout()
    layout.addWidget(widget)
    self.setLayout(layout)
    self.setFixedSize(window_width, window_height)

    background = QPixmap('image-{}.png'.format(crossword_index))
    background = background.scaledToWidth(background.width())
    palette = QPalette()
    palette.setBrush(QPalette.Window, background)
    self.setPalette(palette)

    global status_bar
    status_bar = self.statusBar()

def doPuzzle():
  crossword_index = saveImageAndCluesFromWebsite(date.today() - timedelta(days=1))
  crossword_len = 15

  # Primary data-structure
  # each cell of grid contains 3 integers
  # the first integer is 1 if it is a word cell else 0
  # the second integer is horizontal clue index or 0
  # the third boolean is vertical clue index or 0
  grid = np.zeros((crossword_len, crossword_len, 3), dtype=int)
  convertImageToGrid('image-{}.png'.format(crossword_index), grid)
  #writeTexFile(grid, 'crossword.tex')
  #import pdb;pdb.set_trace()

  grid_cell_length = 30
  shape = grid.shape
  window_width = grid_cell_length * shape[0] * 3
  window_height = grid_cell_length * shape[1] * 1.8
  app = QApplication(sys.argv)
  widget = CrosswordWidget(crossword_index, grid, grid_cell_length)
  window = CrosswordGridWindow(crossword_index, widget, window_width, window_height)
  window.show()
  sys.exit(app.exec_())


if __name__ == '__main__':
  doPuzzle()
