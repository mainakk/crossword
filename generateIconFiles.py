import shutil
import os
import bangla

icons_folder = 'icons'
for root, _, files in os.walk(icons_folder):
  for f in files:
    os.unlink(os.path.join(root, f))

for i in range(1, 100):
  icons_path = os.path.join(icons_folder, '{}.svg'.format(i))
  with open(icons_path, 'wb') as f:
    code = r'<?xml version="1.0" encoding="UTF-8"?>' + '\n'
    code += r'<svg width="12" height="12" xmlns="http://www.w3.org/2000/svg">' + '\n'
    code += r'<text x="0" y="6">' + bangla.convert_english_digit_to_bangla_digit(str(i)) + r'</text>' + '\n'
    code += r'</svg>'
    f.write(code.encode('utf-8'))