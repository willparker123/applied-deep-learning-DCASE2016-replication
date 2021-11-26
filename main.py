#!/usr/bin/env python
# coding: utf-8

# # **AlexNet CNN on CIFAR-10 dataset**
# ### **with PyTorch Transformations**
# 

# In[ ]:


#!/usr/bin/env python3
import time
from multiprocessing import cpu_count
from typing import Union, NamedTuple

import torch
import torch.backends.cudnn
import numpy as np
from torch import nn, optim
from torch.nn import functional as F
import torchvision.datasets
from torch.optim.optimizer import Optimizer
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from torchvision import transforms
import torchvision
from IPython.display import display

import argparse
from pathlib import Path

torch.backends.cudnn.benchmark = True

parser = argparse.ArgumentParser(
    description="Train a simple CNN on CIFAR-10",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
default_dataset_dir = Path.home() / ".cache" / "torch" / "datasets"
parser.add_argument("--dataset-root", default=default_dataset_dir)
parser.add_argument("--log-dir", default=Path("logs"), type=Path)
parser.add_argument("--learning-rate", default=1e-1, type=float, help="Learning rate")
parser.add_argument("--sgd-momentum", default=0.9, type=float, help="SGD Momentum parameter Beta")
parser.add_argument(
    "--batch-size",
    default=128,
    type=int,
    help="Number of images within each mini-batch",
)
parser.add_argument(
    "--epochs",
    default=20,
    type=int,
    help="Number of epochs (passes through the entire dataset) to train for",
)
parser.add_argument(
    "--val-frequency",
    default=2,
    type=int,
    help="How frequently to test the model on the validation set in number of epochs",
)
parser.add_argument(
    "--log-frequency",
    default=10,
    type=int,
    help="How frequently to save logs to tensorboard in number of steps",
)
parser.add_argument(
    "--print-frequency",
    default=10,
    type=int,
    help="How frequently to print progress to the command line in number of steps",
)
parser.add_argument(
    "-j",
    "--worker-count",
    default=cpu_count(),
    type=int,
    help="Number of worker processes used to load data.",
)
parser.add_argument("--data-aug-hflip", action="store_true", help="Applies RandomHorizontalFlip")
parser.add_argument("--data-aug-random-order", action="store_true", help="Applies Transforms in a random order")
parser.add_argument("--data-aug-affine", action="store_true", help="Applies RandomAffine transform")
parser.add_argument(
    "--dropout",
    default=0,
    type=float,
    help="Dropout probability",
)
parser.add_argument(
    "--data-aug-brightness",
    default=0.1,
    type=float,
    help="Brightness parameter in ColorJitter transform",
)
parser.add_argument(
    "--data-aug-contrast",
    default=0,
    type=float,
    help="Contrast parameter in ColorJitter transform",
)
parser.add_argument(
    "--data-aug-saturation",
    default=0,
    type=float,
    help="Saturation parameter in ColorJitter transform",
)
parser.add_argument(
    "--data-aug-hue",
    default=0,
    type=float,
    help="Hue parameter in ColorJitter transform",
)
parser.add_argument(
    "--data-aug-affine-shear",
    default=0.2,
    type=float,
    help="Shear parameter in RandomAffine transform",
)
parser.add_argument(
    "--data-aug-affine-degrees",
    default=45,
    type=float,
    help="Degrees parameter in RandomAffine transform",
)
parser.add_argument("--checkpoint-path", type=Path)
parser.add_argument("--checkpoint-frequency", type=int, default=1, help="Save a checkpoint every N epochs")
parser.add_argument("--resume-checkpoint", type=Path)

class ImageShape(NamedTuple):
    height: int
    width: int
    channels: int


if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
else:
    DEVICE = torch.device("cpu")


def main(args):
    transform_test = transforms.ToTensor()
    train_dataset_test = torchvision.datasets.CIFAR10(
        args.dataset_root, train=True, download=True, transform=transform_test
    )
    test_dataset_test = torchvision.datasets.CIFAR10(
        args.dataset_root, train=False, download=False, transform=transform_test
    )

    dataset_test = torchvision.datasets.CIFAR10('data', download=True, train=True)
    img, label = dataset_test[1]
    print(type(img))
    print(label)
    img

    transform_test = transforms.RandomHorizontalFlip()
    for i in range(5):
      display(img)
      img, label = dataset_test[i]
      img = transform_test(img)
      display(img)
      print(label)

    

    transform = transforms.ToTensor()
    transformList = [transforms.ToTensor()]
    if args.data_aug_hflip is True:
        transformList.insert(0, transforms.RandomHorizontalFlip())
    if args.data_aug_brightness is not 0:
        transformList.insert(0, transforms.ColorJitter(brightness=args.data_aug_brightness, contrast=args.data_aug_contrast, saturation=args.data_aug_saturation, hue=args.data_aug_hue))
    if args.data_aug_affine is True:
        if args.data_aug_affine_shear is not 0:
            transformList.insert(0, transforms.RandomAffine(degrees=args.data_aug_affine_degrees, translate=(0.1, 0.1), shear=[-args.data_aug_affine_shear, args.data_aug_affine_shear, -args.data_aug_affine_shear, args.data_aug_affine_shear]))
        else:
            transformList.insert(0, transforms.RandomAffine(degrees=args.data_aug_affine_degrees, translate=(0.1, 0.1)))
    if len(transformList)>0:
        transform = transforms.Compose([transforms.RandomOrder(transformList.remove(len(transformList)-1)), transforms.ToTensor()] if args.data_aug_random_order else transformList)
    args.dataset_root.mkdir(parents=True, exist_ok=True)
    train_dataset = torchvision.datasets.CIFAR10(
        args.dataset_root, train=True, download=True, transform=transform
    )
    test_dataset = torchvision.datasets.CIFAR10(
        args.dataset_root, train=False, download=False, transform=transform
    )
    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        shuffle=True,
        batch_size=args.batch_size,
        pin_memory=True,
        num_workers=args.worker_count,
    )
    test_loader = torch.utils.data.DataLoader(
        test_dataset,
        shuffle=False,
        batch_size=args.batch_size,
        num_workers=args.worker_count,
        pin_memory=True,
    )

    model = CNN(height=32, width=32, channels=3, class_count=10, dropout=args.dropout)
    if args.resume_checkpoint.exists():
            checkpoint = torch.load(args.resume_checkpoint)
            print(f"Resuming model {args.resume_checkpoint} that achieved {checkpoint['accuracy']}% accuracy")
            model.load_state_dict(checkpoint['model'])
    
    loss_f = nn.CrossEntropyLoss()
    criterion = loss_f  #lambda logits, labels: torch.tensor(0)
    ## TASK 11: Define the optimizer
    optimizer = optim.SGD(model.parameters(), lr=args.learning_rate, momentum=args.sgd_momentum)

    log_dir = get_summary_writer_log_dir(args)
    print(f"Writing logs to {log_dir}")
    summary_writer = SummaryWriter(
            str(log_dir),
            flush_secs=5
    )
    trainer = Trainer(
        model, train_loader, test_loader, criterion, optimizer, summary_writer, DEVICE
    )

    trainer.train(
        args.epochs,
        args.val_frequency,
        print_frequency=args.print_frequency,
        log_frequency=args.log_frequency,
    )
    
    summary_writer.close()



class ImageShape(NamedTuple):
    height: int
    width: int
    channels: int

class CNN(nn.Module):
    def __init__(self, height: int, width: int, channels: int, class_count: int, dropout: float):
        super().__init__()
        self.input_shape = ImageShape(height=height, width=width, channels=channels)
        self.class_count = class_count
        # batch normalise input
        self.bn1 = nn.BatchNorm2d(self.input_shape.channels)
        self.conv1 = nn.Conv2d(
            in_channels=self.input_shape.channels,
            out_channels=32,
            kernel_size=(5, 5),
            padding=(2, 2),
        )
        self.initialise_layer(self.conv1)
        # batch normalise conv1
        self.bn2 = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.conv2 = nn.Conv2d(
            in_channels=32,
            out_channels=64,
            kernel_size=(5, 5),
            padding=(2, 2),
        )
        self.initialise_layer(self.conv2)
        # batch normalise conv2
        self.bn3 = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(kernel_size=(2, 2), stride=(2, 2))
        self.flat1 = nn.Flatten(start_dim=1)
        self.fc1 = nn.Linear(4096, 1024)
        self.initialise_layer(self.fc1)
        self.dropout = nn.Dropout(p=dropout)
        # batch normalise fc1
        self.bn4 = nn.BatchNorm1d(1024)
        self.fc2 = nn.Linear(1024, 10)
        self.initialise_layer(self.fc2)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        # batch normalise input
        x = self.bn1(images)
        x = self.conv1(images)
        # batch normalise X
        x = self.bn2(x)
        x = F.relu(x)
        x = self.pool1(x)
        x = self.conv2(x)
        # batch normalise X
        x = self.bn3(x)
        x = F.relu(x)
        x = self.pool2(x)
        x = self.flat1(x)
        x = self.fc1(x)
        # batch normalise X
        x = self.bn4(x)
        x = F.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x

    @staticmethod
    def initialise_layer(layer):
        if hasattr(layer, "bias"):
            nn.init.zeros_(layer.bias)
        if hasattr(layer, "weight"):
            nn.init.kaiming_normal_(layer.weight)


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion: nn.Module,
        optimizer: Optimizer,
        summary_writer: SummaryWriter,
        device: torch.device,
    ):
        self.model = model.to(device)
        self.device = device
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.criterion = criterion
        self.optimizer = optimizer
        self.summary_writer = summary_writer
        self.step = 0

    def train(
        self,
        epochs: int,
        val_frequency: int,
        print_frequency: int = 20,
        log_frequency: int = 5,
        start_epoch: int = 0
    ):
        self.model.train()
        for epoch in range(start_epoch, epochs):
            self.model.train()
            data_load_start_time = time.time()
            for batch, labels in self.train_loader:
                batch = batch.to(self.device)
                labels = labels.to(self.device)
                data_load_end_time = time.time()



                logits = self.model.forward(batch)
                loss = self.criterion(logits, labels)
                loss.backward()
                self.optimizer.step()
                self.optimizer.zero_grad()

                with torch.no_grad():
                    preds = logits.argmax(-1)
                    accuracy = compute_accuracy(labels, preds)
                    class_accuracy = compute_class_accuracy(labels, preds, self.class_count)

                data_load_time = data_load_end_time - data_load_start_time
                step_time = time.time() - data_load_end_time
                if ((self.step + 1) % log_frequency) == 0:
                    self.log_metrics(epoch, accuracy, loss, data_load_time, step_time)
                if ((self.step + 1) % print_frequency) == 0:
                    self.print_metrics(epoch, accuracy, loss, data_load_time, step_time, class_accuracy)

                self.step += 1
                data_load_start_time = time.time()

            self.summary_writer.add_scalar("epoch", epoch, self.step)
            if ((epoch + 1) % val_frequency) == 0:
                self.validate()
                # self.validate() will put the model in validation mode,
                # so we have to switch back to train mode afterwards
                self.model.train()
            if (epoch + 1) % self.args.checkpoint_frequency or (epoch + 1) == epochs:
                print(f"Saving model to {self.args.checkpoint_path}")
                torch.save({
                    'args': self.args,
                    'model': self.model.state_dict(),
                    'accuracy': accuracy
                }, self.args.checkpoint_path)

    def print_metrics(self, epoch, accuracy, loss, data_load_time, step_time, class_accuracy=None):
        epoch_step = self.step % len(self.train_loader)
        print(
                f"epoch: [{epoch}], "
                f"step: [{epoch_step}/{len(self.train_loader)}], "
                f"batch loss: {loss:.5f}, "
                f"batch accuracy: {accuracy * 100:2.2f}, "+
                (f"class accuracies: {class_accuracy * 100:2.2f}, " if class_accuracy is not None else "")+
                f"data load time: "
                f"{data_load_time:.5f}, "
                f"step time: {step_time:.5f}"
        )

    def log_metrics(self, epoch, accuracy, loss, data_load_time, step_time):
        self.summary_writer.add_scalar("epoch", epoch, self.step)
        self.summary_writer.add_scalars(
                "accuracy",
                {"train": accuracy},
                self.step
        )
        self.summary_writer.add_scalars(
                "loss",
                {"train": float(loss.item())},
                self.step
        )
        self.summary_writer.add_scalar(
                "time/data", data_load_time, self.step
        )
        self.summary_writer.add_scalar(
                "time/data", step_time, self.step
        )

    def validate(self):
        results = {"preds": [], "labels": []}
        total_loss = 0
        self.model.eval()

        # No need to track gradients for validation, we're not optimizing.
        with torch.no_grad():
            for batch, labels in self.val_loader:
                batch = batch.to(self.device)
                labels = labels.to(self.device)
                logits = self.model(batch)
                loss = self.criterion(logits, labels)
                total_loss += loss.item()
                preds = logits.argmax(dim=-1).cpu().numpy()
                results["preds"].extend(list(preds))
                results["labels"].extend(list(labels.cpu().numpy()))

        accuracy = compute_accuracy(
            np.array(results["labels"]), np.array(results["preds"])
        )
        average_loss = total_loss / len(self.val_loader)

        self.summary_writer.add_scalars(
                "accuracy",
                {"test": accuracy},
                self.step
        )
        self.summary_writer.add_scalars(
                "loss",
                {"test": average_loss},
                self.step
        )
        print(f"validation loss: {average_loss:.5f}, accuracy: {accuracy * 100:2.2f}")


def compute_accuracy(
    labels: Union[torch.Tensor, np.ndarray], preds: Union[torch.Tensor, np.ndarray]
) -> float:
    """
    Args:
        labels: ``(batch_size, class_count)`` tensor or array containing example labels
        preds: ``(batch_size, class_count)`` tensor or array containing model prediction
    """
    assert len(labels) == len(preds)
    return float((labels == preds).sum()) / len(labels)

def compute_class_accuracy(
    labels: Union[torch.Tensor, np.ndarray], preds: Union[torch.Tensor, np.ndarray], count: int
) -> float:
    """
    Args:
        labels: ``(batch_size, class_count)`` tensor or array containing example labels
        preds: ``(batch_size, class_count)`` tensor or array containing model prediction
        count: number of different classes
    """
    accuracies = []
    assert len(labels) == len(preds)
    for i in range(count):
        inds = [idx for idx, element in enumerate(labels) if element == i]
        inds_ = torch.Tensor(inds).int()
        ls = torch.index_select(labels, 0, inds_)
        ps = torch.index_select(preds, 0, inds_)
        return float((ls == ps).sum()) / len(ls)

def get_summary_writer_log_dir(args: argparse.Namespace) -> str:
    """Get a unique directory that hasn't been logged to before for use with a TB
    SummaryWriter.

    Args:
        args: CLI Arguments

    Returns:
        Subdirectory of log_dir with unique subdirectory name to prevent multiple runs
        from getting logged to the same TB log directory (which you can't easily
        untangle in TB).
    """
    tb_log_dir_prefix = (
      f"CNN_bn_"
      f"bs={args.batch_size}_"
      f"lr={args.learning_rate}_"
      f"momentum={args.sgd_momentum}_" +
      f"brightness={args.data_aug_brightness}_" +
      (f"saturation={args.data_aug_saturation}_" if args.data_aug_saturation is not 0 else "") +
      (f"contrast={args.data_aug_contrast}_" if args.data_aug_contrast is not 0 else "") +
      f"dropout={args.dropout}_" +
      (f"hue={args.data_aug_hue}_" if args.data_aug_hue is not 0 else "") +
      ("hflip_" if args.data_aug_hflip else "") +
      f"run_"
    )
    i = 0
    while i < 1000:
        tb_log_dir = args.log_dir / (tb_log_dir_prefix + str(i))
        if not tb_log_dir.exists():
            return str(tb_log_dir)
        i += 1
    return str(tb_log_dir)


if __name__ == "__main__":
    main(parser.parse_args())


# In[ ]:



