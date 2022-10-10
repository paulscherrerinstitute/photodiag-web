source /home/photodiag/miniconda3/etc/profile.d/conda.sh
conda activate test

voila --enable_nbextensions=True --no-browser --Voila.ip='0.0.0.0' --port=5007 /home/photodiag/photodiag-web/PBPS.ipynb
