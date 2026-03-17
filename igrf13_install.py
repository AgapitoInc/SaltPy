import requests
import getpass
import os

r = requests.get('https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt')

user = getpass.getuser()
user
folder = f"C:/Users/{user}/.conda/envs/geo3d/lib/site-packages/pyCRGI/data/"
if not os.path.exists(folder):
    os.mkdir(folder)
path = folder + 'igrf13coeffs.txt'
if not os.path.exists(path):
    with open(path,'w') as f:
        f.write(r.text)

if os.path.exists(path):
    print('igrf13coeffs.txt installed. ')