source /opt/miniconda3/etc/profile.d/conda.sh
conda activate test

bokeh serve /opt/photodiag_web/app --port=5011
