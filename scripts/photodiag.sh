source /opt/miniconda3/etc/profile.d/conda.sh
conda activate prod

bokeh serve /opt/photodiag_web/photodiag_web/app --ico-path=none --port=5010
