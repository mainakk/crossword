import shutil
import os

icons_folder = 'icons'
for root, _, files in os.walk(icons_folder):
  for f in files:
    os.unlink(os.path.join(root, f))

for i in range(1, 100):
  icons_path = os.path.join(icons_folder, '{}.svg'.format(i))
  with open(icons_path, 'w') as f:
    f.write(r'<?xml version="1.0"?>' + '\n')
    f.write(r'<svg width="12" height="12" xmlns="http://www.w3.org/2000/svg">' + '\n')
    f.write(r'<text x="0" y="6">' + str(i) + r'</text>' + '\n')
    f.write(r'</svg>' + '\n')
