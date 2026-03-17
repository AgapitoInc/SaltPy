---

  

## Step 1: Create and Configure Conda Environment

  

1.  **Create the environment**

```bash

conda env create -f environment.yml
```
  

2.  **Activate the environment**

```bash

conda activate geo3d
```
  

3. **Make environment available in Jupyter**

```bash

python -m ipykernel install --user --name geo3d --display-name "Python (geo3d)"
```
  

---

  

## Step 2: Add Required Files

  

1.  **Add UTM Grid**

		Download the UTM grid to the following location:

		C:/GIS/World_UTM_Grid.zip

  

2.  **Add IGRF13 Coefficients**

	To install `igrf13coeffs.txt`, either:
		
	- Manually insert the file:

	C:/Users/{your_username}/.conda/envs/geo3d/lib/site-packages/pyCRGI/data/
  

	- Or run the install script:

```bash

python igrf13_install.py
```

  

---


## Step 3: Install SaltPy

```bash

pip install .\saltpy-*-py3-none-any.whl
```

## Step 4: Launch Jupyter 

```bash

jupyter notebook
```
or

```bash

jupyter lab
```
- Open or create a notebook
- Set the kernel to **Python (geo3d)**
- Finally import SaltPy with:

```bash

import saltpy
```
