import torch
import torch.nn as nn
import torch.nn.functional as F


class TorchTBNet(nn.Module):
    """
    Original TB-Net architecture (compatible with old checkpoints):
    conv1 → bn1 → pool
    conv2 → bn2 → pool
    conv3 → bn3 → pool
    fc1 → fc2
    """

    def __init__(self, num_classes=1):
        super(TorchTBNet, self).__init__()

        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.bn1   = nn.BatchNorm2d(32)

        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2   = nn.BatchNorm2d(64)

        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3   = nn.BatchNorm2d(128)

        # Original TB-Net uses hardcoded FC layer input size (128 * 28 * 28)
        self.fc1 = nn.Linear(128 * 28 * 28, 256)
        self.fc2 = nn.Linear(256, num_classes)

    def forward(self, x):
        # (3,224,224)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.max_pool2d(x, 2)        # 112 → 112

        x = F.relu(self.bn2(self.conv2(x)))
        x = F.max_pool2d(x, 2)        # 112 → 56

        x = F.relu(self.bn3(self.conv3(x)))
        x = F.max_pool2d(x, 2)        # 56 → 28

        x = x.view(x.size(0), -1)     # flatten (128*28*28)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)

        return x
