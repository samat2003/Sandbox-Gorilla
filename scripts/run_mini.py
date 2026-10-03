import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
torch.backends.cuda.enable_cudnn_sdp(False)
torch.backends.cudnn.enabled=False
from gorilla.model_server import main
main()
