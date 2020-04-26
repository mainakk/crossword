import cv2
import numpy as np
import math
from bs4 import BeautifulSoup
import requests
import bangla
import crossword
import ipuz
import sys
from PySide2.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide2.QtGui import QColor, QPixmap, QPainter, QFont, QIcon
from PySide2.QtWidgets import QHBoxLayout, QVBoxLayout, QHeaderView, QSizePolicy, QTableView, QWidget, QMainWindow, QApplication
import os

def convertYValToGridVal(y_val):
  y_max = 255
  y_min = 130
  y_min_max = y_min + (y_max - y_min) / 5 # max of y_min
  y_max_min = y_max - (y_max - y_min) / 5 # min of y_max
  return 0 if y_val < y_min_max else 1 if y_val > y_max_min else -1

english_digit_by_bangla_digit = {k : v for k, v in zip(bangla.bangla_number, bangla.english_number)}
def convertBanglaDigitsToEnglishDigits(number):
  for b, e in english_digit_by_bangla_digit.items():
    number = number.replace(b, e)
  return number

def saveImageAndCluesFromWebsite(url, filename):
  headers = requests.utils.default_headers()
  headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'})
  response = requests.get(url, headers)
  soup = BeautifulSoup(response.content, 'html.parser')
  img_url = soup.find('div', class_='crossword-img-1').find('img').attrs['src']
  img_url = 'http:' + img_url
  response = requests.get(img_url, headers)
  with open('image.jpg', 'wb') as f:
    f.write(response.content)

  horizontal_clues = soup.find('div', class_='crosswors-across').text.strip().encode('utf-8')
  vertical_clues = soup.find('div', class_='crosswors-down').text.strip().encode('utf-8')
  with open('horizontal_clues.txt', 'wb') as f:
    f.write(horizontal_clues)

  with open('vertical_clues.txt', 'wb') as f:
    f.write(vertical_clues)

def convertImageToGrid(filename, grid, puzzle):
  image_orig = cv2.imread(filename)
  image_gray = cv2.cvtColor(image_orig, cv2.COLOR_BGR2GRAY)
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
      if not gridVal:
        puzzle[i, j].style = {'background-color': 'black'}

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

def populatePuzzleClues(puzzle):
  with open('horizontal_clues.txt', encoding='utf-8', mode='r') as f:
    for line in f.readlines():
      number, clue = line.strip().split(' ', 1)
      number = convertBanglaDigitsToEnglishDigits(number)
      puzzle.clues.across[number] = clue[:-1]

  with open('vertical_clues.txt', encoding='utf-8', mode='r') as f:
    for line in f.readlines():
      number, clue = line.strip().split(' ', 1)
      number = convertBanglaDigitsToEnglishDigits(number)
      puzzle.clues.down[number] = clue[:-1]

def writeIpuzFile(puzzle, filename):
  ipuz_dict = crossword.to_ipuz(puzzle)
  with open(filename, 'w') as f:
    f.write(ipuz.write(ipuz_dict))

def writeTexFile(grid, filename):
  shape = grid.shape
  latex_code = r'\documentclass{article}' + '\n'
  latex_code += r'\usepackage[banglamainfont=Kalpurush, banglattfont=Siyam Rupali]{latexbangla}' + '\n'
  latex_code += r'\usepackage{cwpuzzle}' + '\n'
  latex_code += r'\begin{document}' + '\n'
  latex_code += r'\begin{Puzzle}{' + str(shape[0]) + '}{' + str(shape[1]) + '}}%\n'
  for i in range(shape[0]):
    latex_code += '\t'
    for j in range(shape[1]):
      latex_code += '|'
      if not grid[i][j][0]:
        latex_code += '*'
      else:
        clue_index = grid[i][j][1] or grid[i][j][2]
        if clue_index:
          latex_code += '[{}]X'.format(clue_index)
        else:
          latex_code += 'X'
    latex_code += '|.\n'
  latex_code += r'\end{Puzzle}' + '\n'

  latex_code += r'\begin{PuzzleClues}{\textbf{Across}}%' + '\n'
  with open('horizontal_clues.txt', encoding='utf-8', mode='r') as f:
    for line in f.readlines():
      number, clue = line.strip().split(' ', 1)
      number = convertBanglaDigitsToEnglishDigits(number)
      latex_code += '\Clue{' + number + '}{}{' + clue + '}%\n'
  latex_code += r'\end{PuzzleClues}%' + '\n'

  latex_code += r'\begin{PuzzleClues}{\textbf{Down}}%' + '\n'
  with open('vertical_clues.txt', encoding='utf-8', mode='r') as f:
    for line in f.readlines():
      number, clue = line.strip().split(' ', 1)
      number = convertBanglaDigitsToEnglishDigits(number)
      latex_code += '\Clue{' + number + '}{}{' + clue + '}%\n'
  latex_code += r'\end{PuzzleClues}%' + '\n'

  latex_code += r'\end{document}'
  with open(filename, 'wb') as f:
    f.write(latex_code.encode('utf-8'))

icons_folder = 'icons'
class CrosswordGridModel(QAbstractTableModel):
  def __init__(self, grid_data=None):
    QAbstractTableModel.__init__(self)
    self.load_grid_data(grid_data)

  def load_grid_data(self, grid_data):
    self.grid_data = grid_data
    shape = grid_data.shape
    self.row_count = shape[0]
    self.column_count = shape[1]
    self.solution_data = np.full((shape[0], shape[1]), '', dtype=object)

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
    elif role == Qt.DecorationRole:
      if clue_index:
        icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
        return QIcon(icon_path)
      else:
        return None
    elif role == Qt.BackgroundRole:
      return QColor(Qt.white) if is_word_cell else QColor(Qt.black)
    return None

  def setData(self, index, value, role=Qt.EditRole):
    row = index.row()
    column = index.column()
    if role == Qt.EditRole:
      self.solution_data[row][column] = value
      return True
    return False

class CrosswordClueModel(QAbstractTableModel):
  def __init__(self, clue_data=None, clue_type=''):
    QAbstractTableModel.__init__(self)
    self.load_clue_data(clue_data)
    self.clue_type = clue_type

  def load_clue_data(self, clue_data):
    self.clue_data = []
    for number, clue in clue_data:
      self.clue_data.append((number, clue))
    self.row_count = len(self.clue_data)
    self.column_count = 2

  def rowCount(self, parent=QModelIndex()):
    return self.row_count

  def columnCount(self, parent=QModelIndex()):
    return self.column_count

  def headerData(self, section, orientation, role):
    if role != Qt.DisplayRole:
        return None
    if orientation == Qt.Horizontal:
        return ('', self.clue_type)[section]
    else:
        return ''

  def flags(self, index):
    return Qt.ItemIsEnabled

  def data(self, index, role=Qt.DisplayRole):
    row = index.row()
    column = index.column()
    cell_data = self.clue_data[row][column]

    if role == Qt.DisplayRole:
      return cell_data
    return None

class CrosswordWidget(QWidget):
  def __init__(self, grid_data, grid_cell_length, clue_across_data, clue_down_data):
      QWidget.__init__(self)
      self.grid_model = CrosswordGridModel(grid_data)
      self.grid_table_view = QTableView()
      self.grid_table_view.setModel(self.grid_model)

      self.grid_horizontal_header = self.grid_table_view.horizontalHeader()
      self.grid_horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
      self.grid_horizontal_header.setDefaultSectionSize(grid_cell_length)
      self.grid_horizontal_header.hide()
      self.grid_vertical_header = self.grid_table_view.verticalHeader()
      self.grid_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
      self.grid_vertical_header.setDefaultSectionSize(grid_cell_length)
      self.grid_vertical_header.hide()

      self.clue_across_model = CrosswordClueModel(clue_across_data, 'পাশাপাশি')
      self.clue_across_table_view = QTableView()
      self.clue_across_table_view.setModel(self.clue_across_model)
      self.clue_across_horizontal_header = self.clue_across_table_view.horizontalHeader()
      self.clue_across_horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
      self.clue_across_vertical_header = self.clue_across_table_view.verticalHeader()
      self.clue_across_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
      self.clue_across_vertical_header.setDefaultSectionSize(grid_cell_length)

      self.clue_down_model = CrosswordClueModel(clue_down_data, 'উপর নীচে')
      self.clue_down_table_view = QTableView()
      self.clue_down_table_view.setModel(self.clue_down_model)
      self.clue_down_horizontal_header = self.clue_down_table_view.horizontalHeader()
      self.clue_down_horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
      self.clue_down_vertical_header = self.clue_down_table_view.verticalHeader()
      self.clue_down_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
      self.clue_down_vertical_header.setDefaultSectionSize(grid_cell_length)

      self.clue_layout = QHBoxLayout()
      self.clue_layout.addWidget(self.clue_across_table_view)
      self.clue_layout.addWidget(self.clue_down_table_view)
      self.clue_widget = QWidget()
      self.clue_widget.setLayout(self.clue_layout)

      self.main_layout = QVBoxLayout()
      self.main_layout.addWidget(self.grid_table_view)
      self.main_layout.addWidget(self.clue_widget)
      self.setLayout(self.main_layout)

class CrosswordGridWindow(QMainWindow):
  def __init__(self, widget, window_width, window_height):
    QMainWindow.__init__(self)
    self.setCentralWidget(widget)
    self.setFixedSize(window_width, window_height)

def doPuzzle():
  url = 'https://www.anandabazar.com/others/crossword'
  filename = 'image.jpg'
  #saveImageAndCluesFromWebsite(url, filename)
  crossword_len = 15

  # Primary data-structure
  # each cell of grid contains 3 integers
  # the first integer is 1 if it is a word cell else 0
  # the second integer is horizontal clue index or 0
  # the third boolean is vertical clue index or 0
  grid = np.zeros((crossword_len, crossword_len, 3), dtype=int)
  puzzle = crossword.Crossword(crossword_len, crossword_len) # Secondary data-structure
  puzzle.meta.kind = 'http://ipuz.org/crossword#1'
  convertImageToGrid(filename, grid, puzzle)
  populatePuzzleClues(puzzle)
  writeIpuzFile(puzzle, 'crossword.ipuz')
  #writeTexFile(grid, 'crossword.tex')
  #import pdb;pdb.set_trace()

  grid_cell_length = 24
  shape = grid.shape
  window_width = grid_cell_length * shape[0] * 2
  window_height = grid_cell_length * shape[1] * 2.5

  app = QApplication(sys.argv)
  widget = CrosswordWidget(grid, grid_cell_length, puzzle.clues.across(), puzzle.clues.down())
  window = CrosswordGridWindow(widget, window_width, window_height)
  window.show()
  sys.exit(app.exec_())


if __name__ == '__main__':
  doPuzzle()
