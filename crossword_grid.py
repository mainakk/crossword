import cv2
import numpy as np
import math
import os
import sys
from datetime import date, timedelta
import requests
from PySide2.QtCore import QSize, QAbstractTableModel, Qt
from PySide2.QtGui import QPixmap, QPalette, QColor
from PySide2.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QVBoxLayout, QTableWidget, \
  QStyledItemDelegate, QTableView, QLabel, QHBoxLayout, QGridLayout, QToolBar, QDialogButtonBox

url_format = 'https://epaper.anandabazar.com/epaperimages////{}////{}-md-hr-2ll.png'

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
  def __init__(self, parent=None):
    super(CrosswordGridModel, self).__init__(parent)

  def rowCount(self, parent):
    return grid_row_count

  def columnCount(self, parent):
    return grid_column_count

  def data(self, index, role):
    if role == Qt.DisplayRole:
      return str((index.row() * grid_column_count + index.column()) % 100)
    elif role == Qt.BackgroundRole:
      return QColor(Qt.white)

class Form(QDialog):
  def __init__(self, parent=None):
    super(Form, self).__init__(parent)
    self.setWindowTitle("Crossword")
    self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    tableModel = CrosswordGridModel(self)
    tableView = QTableView(self)
    tableView.horizontalHeader().hide()
    tableView.verticalHeader().hide()
    #tableView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    #tableView.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tableView.setModel(tableModel)
    for i in range(grid_row_count):
      tableView.setRowHeight(i, grid_cell_size)
    for i in range(grid_column_count):
      tableView.setColumnWidth(i, grid_cell_size)
    print(tableView.rowHeight(10))
    print(tableView.columnWidth(10))

    #rect = tableView.geometry()
    #rect.setWidth(tableView.columnWidth(0) * grid_column_count + grid_column_count - 1)
    #tableView.setGeometry(rect)

    right_label = QLabel(self)
    right_pixmap = QPixmap('right_clues.png')
    right_label.setPixmap(right_pixmap)

    down_label = QLabel(self)
    down_pixmap = QPixmap('down_clues.png')
    down_label.setPixmap(down_pixmap)

    bbox = QDialogButtonBox(self)
    saveButton = bbox.addButton('Save progress', QDialogButtonBox.AcceptRole)
    loadButton = bbox.addButton('Load progress', QDialogButtonBox.AcceptRole)
    clearButton = bbox.addButton('Clear progress', QDialogButtonBox.AcceptRole)

    layout = QGridLayout(self)
    layout.addWidget(tableView, 0, 0, 2, 1)
    layout.addWidget(right_label, 0, 1, Qt.AlignLeft | Qt.AlignTop)
    layout.addWidget(bbox, 1, 1, Qt.AlignHCenter | Qt.AlignBottom)
    layout.addWidget(down_label, 2, 0, Qt.AlignLeft | Qt.AlignTop)
    self.setLayout(layout)

    windowWidth = tableView.columnWidth(0) * grid_column_count + grid_column_count - 1 + right_clues_right - right_clues_left + layout.horizontalSpacing() + 10
    windowHeight = tableView.rowHeight(0) * grid_row_count + grid_row_count - 1 + down_clues_bottom - down_clues_top + layout.verticalSpacing() + 18
    self.resize(QSize(windowWidth, windowHeight))

if __name__ == '__main__':
  crossword_index = saveImageAndCluesFromWebsite(date.today())
  grid = np.zeros((grid_column_count, grid_row_count, 3), dtype=int)
  imgFile = 'image-{}.png'.format(crossword_index)
  convertImageToGrid(imgFile, grid)
  saveClueImages(imgFile)

  app = QApplication(sys.argv)
  form = Form()
  form.show()
  sys.exit(app.exec_())