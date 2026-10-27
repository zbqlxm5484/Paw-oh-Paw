_base_ = ["/work/ssafy/paw_eval/models/fs-v4/pose.py"]

data_root = "/data/train_set"
train_ann = "annotations_46.json"
meta_file = "/exp/train/creamoff46.py"
max_epochs = 30
base_lr = 1e-4
batch = 16

load_from = "/work/ssafy/paw_eval/models/fs-v4/pose.pth"
randomness = dict(seed=42)

codec = dict(type="SimCCLabel", input_size=(192, 256), sigma=(4.9, 5.66), simcc_split_ratio=2.0,
             normalize=False, use_dark=False)

model = dict(backbone=dict(norm_eval=True))

train_pipeline = [
    dict(type="LoadImage", backend_args=None),
    dict(type="GetBBoxCenterScale", padding=1.25),
    dict(type="RandomFlip", direction="horizontal"),
    dict(type="RandomBBoxTransform", scale_factor=[0.75, 1.25], rotate_factor=30),
    dict(type="TopdownAffine", input_size=codec["input_size"]),
    dict(type="GenerateTarget", encoder=codec),
    dict(type="PackPoseInputs"),
]

train_dataloader = dict(
    batch_size=batch,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=True),
    dataset=dict(
        type="CocoDataset",
        data_root=data_root,
        data_mode="topdown",
        ann_file=train_ann,
        data_prefix=dict(img=""),
        metainfo=dict(from_file=meta_file),
        pipeline=train_pipeline,
    ),
)

train_cfg = dict(by_epoch=True, max_epochs=max_epochs, val_interval=1000)
val_cfg = None
val_dataloader = None
val_evaluator = None
test_cfg = None
test_evaluator = None
test_dataloader = None

optim_wrapper = dict(type="OptimWrapper", optimizer=dict(type="AdamW", lr=base_lr, weight_decay=0.05),
                     paramwise_cfg=dict(norm_decay_mult=0, bias_decay_mult=0))
param_scheduler = [
    dict(type="LinearLR", start_factor=1.0e-3, by_epoch=False, begin=0, end=200),
    dict(type="CosineAnnealingLR", eta_min=base_lr * 0.05, begin=0, end=max_epochs, T_max=max_epochs, by_epoch=True),
]

default_hooks = dict(
    checkpoint=dict(type="CheckpointHook", interval=5, max_keep_ckpts=2, save_optimizer=False),
    logger=dict(type="LoggerHook", interval=10),
)
custom_hooks = []
