source /home/photodiag/miniconda3/etc/profile.d/conda.sh
conda activate prod

voila --enable_nbextensions=True --no-browser --Voila.ip='0.0.0.0' --port=5006 /home/photodiag/photodiag-web/PBPS.ipynb
