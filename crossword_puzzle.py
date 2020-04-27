import cv2
import numpy as np
import math
from bs4 import BeautifulSoup
import requests
import bangla
import crossword
import ipuz
import sys
from PySide2.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer
from PySide2.QtGui import QColor, QPixmap, QPainter, QFont, QIcon
from PySide2.QtWidgets import QHBoxLayout, QVBoxLayout, QHeaderView, QSizePolicy, QTableView, QWidget, QMainWindow, QApplication, QPushButton
import os
import datetime

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

def needToFetchFromWebsite():
  try:
    with open('crossword-index.txt', 'r') as f:
      crossword_index = int(f.readline().strip())
      todays_index = (datetime.date.today() - datetime.date(2020, 4, 27)).days + 7606
      return todays_index > crossword_index
  except IOError:
    return True

def saveImageAndCluesFromWebsite(url):
  headers = requests.utils.default_headers()
  headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'})
  response = requests.get(url, headers)
  soup = BeautifulSoup(response.content, 'html.parser')
  img_div = soup.find('div', class_='crossword-img-1')
  header = img_div.parent.find('h2').string
  crossword_index = convertBanglaDigitsToEnglishDigits(header.strip().split()[-1])
  with open('crossword-index.txt', 'w') as f:
    f.write(crossword_index)

  img_url = img_div.find('img').attrs['src']
  img_url = 'http:' + img_url
  response = requests.get(img_url, headers)
  with open('image-{}.jpg'.format(crossword_index), 'wb') as f:
    f.write(response.content)

  horizontal_clues = soup.find('div', class_='crosswors-across').text.strip().encode('utf-8')
  vertical_clues = soup.find('div', class_='crosswors-down').text.strip().encode('utf-8')
  with open('horizontal-clues-{}.txt'.format(crossword_index), 'wb') as f:
    f.write(horizontal_clues)

  with open('vertical-clues-{}.txt'.format(crossword_index), 'wb') as f:
    f.write(vertical_clues)

  print('Crossword {} has been fetched from website'.format(crossword_index))
  return crossword_index

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

def populatePuzzleClues(crossword_index, puzzle):
  with open('horizontal-clues-{}.txt'.format(crossword_index), encoding='utf-8', mode='r') as f:
    for line in f.readlines():
      number, clue = line.strip().split(' ', 1)
      number = convertBanglaDigitsToEnglishDigits(number)
      puzzle.clues.across[number] = clue[:-1]

  with open('vertical-clues-{}.txt'.format(crossword_index), encoding='utf-8', mode='r') as f:
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

status_bar = None
icons_folder = 'icons'
font_name ='Kalpurush'
font_size = 13
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

  def save_solution(self):
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
    elif role == Qt.DecorationRole:
      if clue_index:
        icon_path = os.path.join(icons_folder, '{}.svg'.format(clue_index))
        return QIcon(icon_path)
      else:
        return None
    elif role == Qt.BackgroundRole:
      return QColor(Qt.white) if is_word_cell else QColor(Qt.black)
    elif role == Qt.FontRole:
      font = QFont(font_name, 10)
      return font
    return None

  def setData(self, index, value, role=Qt.EditRole):
    row = index.row()
    column = index.column()
    if role == Qt.EditRole:
      print(value)
      self.solution_data[row][column] = value
      if status_bar:
        status_bar.clearMessage()
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
      bangla_number = bangla.convert_english_digit_to_bangla_digit(str(number))
      self.clue_data.append((bangla_number, clue))
    self.row_count = len(self.clue_data)
    self.column_count = 2

  def rowCount(self, parent=QModelIndex()):
    return self.row_count

  def columnCount(self, parent=QModelIndex()):
    return self.column_count

  def headerData(self, section, orientation, role):
    if role == Qt.DisplayRole:
        return ('', self.clue_type)[section] if orientation == Qt.Horizontal else ''
    elif role == Qt.FontRole:
      font = QFont(font_name, font_size, QFont.Bold)
      return font
    return None

  def flags(self, index):
    return Qt.ItemIsEnabled

  def data(self, index, role=Qt.DisplayRole):
    row = index.row()
    column = index.column()
    cell_data = self.clue_data[row][column]

    if role == Qt.DisplayRole:
      return cell_data
    elif role == Qt.FontRole:
      font = QFont(font_name, font_size)
      return font
    return None

class CrosswordWidget(QWidget):
  def __init__(self, crossword_index, grid_data, grid_cell_length, clue_across_data, clue_down_data):
    QWidget.__init__(self)
    self.grid_model = CrosswordGridModel(crossword_index, grid_data)
    self.grid_table_view = QTableView(self)
    self.grid_table_view.setModel(self.grid_model)
    self.grid_horizontal_header = self.grid_table_view.horizontalHeader()
    self.grid_horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
    self.grid_horizontal_header.setDefaultSectionSize(grid_cell_length)
    self.grid_horizontal_header.hide()
    self.grid_vertical_header = self.grid_table_view.verticalHeader()
    self.grid_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
    self.grid_vertical_header.setDefaultSectionSize(grid_cell_length * 1.3)
    self.grid_vertical_header.hide()

    self.clue_across_model = CrosswordClueModel(clue_across_data, 'পাশাপাশি')
    self.clue_across_table_view = QTableView(self)
    self.clue_across_table_view.setModel(self.clue_across_model)
    self.clue_across_horizontal_header = self.clue_across_table_view.horizontalHeader()
    self.clue_across_horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
    self.clue_across_vertical_header = self.clue_across_table_view.verticalHeader()
    self.clue_across_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
    self.clue_across_vertical_header.setDefaultSectionSize(grid_cell_length)
    self.clue_down_model = CrosswordClueModel(clue_down_data, 'উপর নীচে')
    self.clue_down_table_view = QTableView(self)
    self.clue_down_table_view.setModel(self.clue_down_model)
    self.clue_down_horizontal_header = self.clue_down_table_view.horizontalHeader()
    self.clue_down_horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
    self.clue_down_vertical_header = self.clue_down_table_view.verticalHeader()
    self.clue_down_vertical_header.setSectionResizeMode(QHeaderView.Fixed)
    self.clue_down_vertical_header.setDefaultSectionSize(grid_cell_length)

    self.clue_layout = QHBoxLayout(self)
    self.clue_layout.addWidget(self.clue_across_table_view)
    self.clue_layout.addWidget(self.clue_down_table_view)
    self.clue_widget = QWidget(self)
    self.clue_widget.setLayout(self.clue_layout)

    self.buttons_layout = QHBoxLayout(self)
    self.save_button = QPushButton("Save")
    self.load_button = QPushButton("Load")
    self.clear_button = QPushButton("Clear")
    self.save_button.clicked.connect(self.save_solution)
    self.load_button.clicked.connect(self.grid_model.load_solution)
    self.clear_button.clicked.connect(self.grid_model.clear_solution)
    self.buttons_layout.addWidget(self.save_button)
    self.buttons_layout.addWidget(self.load_button)
    self.buttons_layout.addWidget(self.clear_button)
    self.buttons_widget = QWidget(self)
    self.buttons_widget.setLayout(self.buttons_layout)

    self.grid_layout = QVBoxLayout(self)
    self.grid_layout.addWidget(self.grid_table_view)
    self.grid_layout.addWidget(self.buttons_widget)
    self.grid_widget = QWidget(self)
    self.grid_widget.setLayout(self.grid_layout)

    self.main_layout = QHBoxLayout(self)
    self.main_layout.addWidget(self.grid_widget)
    self.main_layout.addWidget(self.clue_widget)
    self.setLayout(self.main_layout)

  def save_solution(self):
    if self.grid_model.save_solution():
      status_bar.showMessage("Solution saved")

class CrosswordGridWindow(QMainWindow):
  def __init__(self, crossword_index, widget, window_width, window_height):
    QMainWindow.__init__(self)
    date = datetime.date.today().strftime("%A, %d %B, %Y")
    self.setWindowTitle('শব্দছক ' + bangla.convert_english_digit_to_bangla_digit(crossword_index) + '   ' + date)
    self.setCentralWidget(widget)
    self.setFixedSize(window_width, window_height)
    global status_bar
    status_bar = self.statusBar()

def doPuzzle():
  url = 'https://www.anandabazar.com/others/crossword'
  if needToFetchFromWebsite():
    crossword_index = saveImageAndCluesFromWebsite(url)
  else:
    with open('crossword-index.txt', 'r') as f:
      crossword_index = f.readline().strip()
  crossword_len = 15

  # Primary data-structure
  # each cell of grid contains 3 integers
  # the first integer is 1 if it is a word cell else 0
  # the second integer is horizontal clue index or 0
  # the third boolean is vertical clue index or 0
  grid = np.zeros((crossword_len, crossword_len, 3), dtype=int)
  puzzle = crossword.Crossword(crossword_len, crossword_len) # Secondary data-structure
  puzzle.meta.kind = 'http://ipuz.org/crossword#1'
  convertImageToGrid('image-{}.jpg'.format(crossword_index), grid, puzzle)
  populatePuzzleClues(crossword_index, puzzle)
  #writeIpuzFile(puzzle, 'crossword.ipuz')
  #writeTexFile(grid, 'crossword.tex')
  #import pdb;pdb.set_trace()

  grid_cell_length = 30
  shape = grid.shape
  window_width = grid_cell_length * shape[0] * 3
  window_height = grid_cell_length * shape[1] * 1.8
  app = QApplication(sys.argv)
  widget = CrosswordWidget(crossword_index, grid, grid_cell_length, puzzle.clues.across(), puzzle.clues.down())
  window = CrosswordGridWindow(crossword_index, widget, window_width, window_height)
  window.show()
  sys.exit(app.exec_())


if __name__ == '__main__':
  doPuzzle()
