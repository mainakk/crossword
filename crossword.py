import cv2
import numpy as np
import math
from bs4 import BeautifulSoup
import requests
import imutils

def convertYValToGridVal(y_val):
  y_max = 255
  y_min = 130
  y_min_max = y_min + (y_max - y_min) / 5 # max of y_min
  y_max_min = y_max - (y_max - y_min) / 5 # min of y_max
  return 0 if y_val < y_min_max else 1 if y_val > y_max_min else -1

def saveImageFromWebsite(url, filename):
  headers = requests.utils.default_headers()
  headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'})
  response = requests.get(url, headers)
  soup = BeautifulSoup(response.content, 'html.parser')
  img_url = soup.find('div', class_='crossword-img-1').find('img').attrs['src']
  img_url = 'http:' + img_url
  response = requests.get(img_url, headers)

  with open('image.jpg', 'wb') as f:
    f.write(response.content)

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

def printLatexCode(grid):
  shape = grid.shape
  code = r'\begin{Puzzle}{' + str(shape[0]) + '}{' + str(shape[1]) + '}}%\n'
  for i in range(shape[0]):
    code += '\t'
    for j in range(shape[1]):
      code += '|'
      if not grid[i][j][0]:
        code += '*'
      else:
        clue_index = grid[i][j][1] or grid[i][j][2]
        if clue_index:
          code += '[{}]X'.format(clue_index)
        else:
          code += 'X'
    code += '|.\n'
  code += r'\end{Puzzle}'
  print(code)

url = 'https://www.anandabazar.com/others/crossword'
filename = 'image.jpg'
saveImageFromWebsite(url, filename)
grid = convertImageToGrid(filename)
printLatexCode(grid)
