import cv2
import numpy as np
import math
from bs4 import BeautifulSoup
import requests
import bangla

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

def convertImageToGrid(filename):
  image_orig = cv2.imread(filename)
  image_gray = cv2.cvtColor(image_orig, cv2.COLOR_BGR2GRAY)
  nrows, ncols = image_gray.shape

  crossword_len = 15

  # each cell of grid contains 3 integers
  # the first integer is 0 if it is a word cell else 1
  # the second integer is horizontal clue index or 0
  # the third boolean is vertical clue index or 0
  grid = np.zeros((crossword_len, crossword_len, 3), dtype=int)
  for i in range(crossword_len):
    for j in range(crossword_len):
      xmin = math.ceil(ncols * j / crossword_len)
      xmax = math.floor(ncols * (j + 1) / crossword_len)
      ymin = math.ceil(nrows * i / crossword_len)
      ymax = math.floor(nrows * (i + 1) / crossword_len)
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
  for i in range(crossword_len):
    for j in range(crossword_len):
      if not grid[i][j][0]:
        continue
      found_horizontal = False
      if (j == 0 or not grid[i][j - 1][0]) and j != crossword_len - 1 and grid[i][j + 1][0]:
        clue_index += 1
        grid[i][j][1] = clue_index
        found_horizontal = True
      if (i == 0 or not grid[i - 1][j][0]) and i != crossword_len - 1 and grid[i + 1][j][0]:
        if not found_horizontal:
          clue_index += 1
        grid[i][j][2] = clue_index
  return grid

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

url = 'https://www.anandabazar.com/others/crossword'
filename = 'image.jpg'
#saveImageAndCluesFromWebsite(url, filename)
grid = convertImageToGrid(filename)
writeTexFile(grid, 'crossword.tex')
