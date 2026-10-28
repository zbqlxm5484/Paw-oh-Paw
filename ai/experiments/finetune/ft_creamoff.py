# fs-v4(RTMPose-m) 를 크림오프 사람 라벨로 이어 학습 (10-22 준비).
# 같은 폴더에 전달본 model/pose.py 를 복사해 둔다. 46점 출력 중 앞 22점만 라벨이 있고 aux 24점은 가시성 0.
# 데이터 경로는 train.py --cfg-options 로 바꾼다.
_base_ = ["./pose.py"]

FLIP = [
    1,
    0,
    2,
    8,
    9,
    10,
    11,
    12,
    3,
    4,
    5,
    6,
    7,
    13,
    18,
    19,
    20,
    21,
    14,
    15,
    16,
    17,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    30,
    29,
    31,
    32,
    33,
    37,
    38,
    39,
    34,
    35,
    36,
    43,
    44,
    45,
    40,
    41,
    42,
]
NAMES = [f"kp{i}" for i in range(46)]
metainfo = dict(
    dataset_name="pose46",
    keypoint_info={
        i: dict(
            name=NAMES[i],
            id=i,
            color=[255, 128, 0],
            type="upper",
            swap=NAMES[FLIP[i]] if FLIP[i] != i else "",
        )
        for i in range(46)
    },
    skeleton_info={},
    joint_weights=[1.0] * 46,
    sigmas=[0.05] * 46,
)

codec = dict(
    type="SimCCLabel",
    input_size=(192, 256),
    sigma=(4.9, 5.66),
    simcc_split_ratio=2.0,
    normalize=False,
    use_dark=False,
)
train_pipeline = [
    dict(type="LoadImage"),
    dict(type="GetBBoxCenterScale"),
    dict(type="RandomFlip", direction="horizontal"),
    dict(type="RandomBBoxTransform", scale_factor=[0.8, 1.2], rotate_factor=15),
    dict(type="TopdownAffine", input_size=(192, 256)),
    dict(type="GenerateTarget", encoder=codec),
    dict(type="PackPoseInputs"),
]
val_pipeline = [
    dict(type="LoadImage"),
    dict(type="GetBBoxCenterScale"),
    dict(type="TopdownAffine", input_size=(192, 256)),
    dict(type="PackPoseInputs"),
]
_ds = dict(
    type="CocoDataset",
    data_root="/content/data/img/",
    data_mode="topdown",
    metainfo=metainfo,
    data_prefix=dict(img=""),
)
train_dataloader = dict(
    batch_size=32,
    num_workers=4,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=True),
    dataset=dict(_ds, ann_file="/content/data/train46.json", pipeline=train_pipeline),
)
val_dataloader = dict(
    batch_size=64,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=False),
    dataset=dict(_ds, ann_file="/content/data/val46.json", pipeline=val_pipeline, test_mode=True),
)
test_dataloader = val_dataloader
val_evaluator = [
    dict(type="PCKAccuracy", thr=0.1, norm_item="bbox"),
    dict(type="PCKAccuracy", thr=0.05, norm_item="bbox", prefix="pck05"),
]
test_evaluator = val_evaluator

max_epochs = 10
train_cfg = dict(by_epoch=True, max_epochs=max_epochs, val_interval=1)
val_cfg = dict()
test_cfg = dict()
optim_wrapper = dict(
    type="AmpOptimWrapper",
    optimizer=dict(type="AdamW", lr=5e-5, weight_decay=0.05),
    paramwise_cfg=dict(norm_decay_mult=0, bias_decay_mult=0),
)
param_scheduler = [
    dict(type="LinearLR", start_factor=0.1, by_epoch=False, begin=0, end=100),
    dict(
        type="CosineAnnealingLR",
        eta_min=1e-7,
        by_epoch=True,
        begin=0,
        end=max_epochs,
        convert_to_iter_based=True,
    ),
]
load_from = "./pose.pth"
default_hooks = dict(
    timer=dict(type="IterTimerHook"),
    logger=dict(type="LoggerHook", interval=20),
    param_scheduler=dict(type="ParamSchedulerHook"),
    checkpoint=dict(
        type="CheckpointHook", interval=1, max_keep_ckpts=3, save_best="PCK", rule="greater"
    ),
    sampler_seed=dict(type="DistSamplerSeedHook"),
)
env_cfg = dict(
    cudnn_benchmark=False, mp_cfg=dict(mp_start_method="fork"), dist_cfg=dict(backend="nccl")
)
log_processor = dict(type="LogProcessor", window_size=20, by_epoch=True)
log_level = "INFO"
resume = False
randomness = dict(seed=42)
visualizer = dict(type="PoseLocalVisualizer", vis_backends=[dict(type="LocalVisBackend")])

model = dict(
    backbone=dict(norm_eval=True),  # BN 통계 고정: 안 하면 학습률 0 이어도 KPI-04 8.03→10.96°
    test_cfg=dict(flip_test=True),
)  # 10-20 시험에서 유일하게 이긴 설정
