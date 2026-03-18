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

  

## Step 2: Install SaltPy

```bash

pip install .\saltpy-*-py3-none-any.whl
```

## Step 3: Launch Jupyter 

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
