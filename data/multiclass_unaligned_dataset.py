import os.path
import re
import torch
import random
import numpy as np
from data.base_dataset import BaseDataset, get_transform
from data.dataset_utils import list_folder_images
from PIL import Image
from pdb import set_trace as st

TEX_CLASSES_UPPER_BOUNDS = [2, 6, 9, 14, 19, 29, 39, 49, 69, 120]

class MulticlassUnalignedDataset(BaseDataset):
    def initialize(self, opt):
        self.opt = opt
        self.root = opt.dataroot
        self.name_mapping = {}
        self.prev_A = -1
        self.prev_B = -1
        self.class_A = -1
        self.class_B = -1
        self.get_samples = False

        # find all existing classes in root
        self.tempClassNames = []
        subDirs = next(os.walk(self.root))[1]  # a quick way to get all subdirectories
        for currDir in subDirs:
            if self.opt.isTrain:
                prefix = 'train'
            else:
                prefix = 'test'
            if prefix in currDir:  # we assume that the class name starts with the prefix
                len_prefix = len(prefix)
                className = currDir[len_prefix:]
                self.tempClassNames += [className]

        # sort classes
        if len(self.opt.sort_order) > 0:
            self.classNames = []
            for i, nextClass in enumerate(self.opt.sort_order):
                for currClass in self.tempClassNames:
                    if nextClass == currClass:
                        self.classNames += [currClass]
                        curr_class_num = self.assign_tex_class(currClass)
                        self.name_mapping[currClass] = curr_class_num
        else:
            self.classNames = sorted(self.tempClassNames)
            for i, currClass in enumerate(self.classNames):
                curr_class_num = self.assign_tex_class(currClass)
                self.name_mapping[currClass] = curr_class_num

        self.active_classes_mapping = {}
        self.inv_active_classes_mapping = {}

        for i, name in enumerate(self.classNames):
            self.active_classes_mapping[i] = self.name_mapping[name]
            self.inv_active_classes_mapping[self.name_mapping[name]] = i

        self.numClasses = len(self.classNames)
        opt.numClasses = self.numClasses
        opt.classNames = self.classNames
        opt.active_classes_mapping = self.active_classes_mapping

        # set class counter for test mode
        if self.opt.isTrain is False:
            opt.batchSize = self.numClasses
            self.class_counter = 0
            self.img_counter = 0

        # arrange directories
        self.dirs = []
        self.img_paths = []
        self.parsing_paths = []
        self.sizes = []

        for currClass in self.classNames:
            self.dirs += [os.path.join(opt.dataroot, opt.phase + currClass)]
            imgs, parsings = list_folder_images(self.dirs[-1], self.opt, None)
            self.img_paths += [imgs]
            self.parsing_paths += [parsings]
            self.sizes += [len(self.img_paths[-1])]

        opt.dataset_size = self.__len__()
        self.transform = get_transform(opt)

    def assign_tex_class(self, class_name):
        ages = [int(s) for s in re.split('-|_', class_name) if s.isdigit()]
        max_age = ages[-1]
        for i in range(len(TEX_CLASSES_UPPER_BOUNDS)):
            if max_age <= TEX_CLASSES_UPPER_BOUNDS[i]:
                break

        return i

    def mask_image(self, img, parsings):
        labels_to_mask = [0,14,15,16,18]
        for idx in labels_to_mask:
            img[parsings == idx] = 127.5

        return img

    def get_item_from_path(self, path):
        path_dir, im_name = os.path.split(path)
        try:
            img = Image.open(path + '.jpg').convert('RGB')
        except:
            img = Image.open(path + '.png').convert('RGB')

        img = np.array(img.getdata(), dtype=np.uint8).reshape(img.size[1], img.size[0], 3)

        parsing_path = os.path.join(path_dir, 'parsings', im_name + '.png')
        parsing = Image.open(parsing_path).convert('L')
        parsing = np.array(parsing.getdata(), dtype=np.uint8).reshape(parsing.size[1], parsing.size[0], 1)
        img = self.mask_image(img, parsing)
        img = self.transform(img)

        return {'Imgs': img,
                'Paths': [path],
                'Classes': torch.zeros(1,dtype=torch.int),
                'Valid': True}

    def __getitem__(self, index):
        if self.opt.isTrain:# and not self.get_samples:
            condition = True
            self.class_A_idx = random.randint(0,self.numClasses - 1)
            self.class_A = self.active_classes_mapping[self.class_A_idx]
            while condition:
                self.class_B_idx = random.randint(0,self.numClasses - 1)
                self.class_B = self.active_classes_mapping[self.class_B_idx]
                condition = self.class_A == self.class_B

            index_A = random.randint(0, self.sizes[self.class_A_idx] - 1)
            index_B = random.randint(0, self.sizes[self.class_B_idx] - 1)

            A_img_path = self.img_paths[self.class_A_idx][index_A]
            A_img = Image.open(A_img_path).convert('RGB')
            A_img = np.array(A_img.getdata(), dtype=np.uint8).reshape(A_img.size[1], A_img.size[0], 3)

            B_img_path = self.img_paths[self.class_B_idx][index_B]
            B_img = Image.open(B_img_path).convert('RGB')
            B_img = np.array(B_img.getdata(), dtype=np.uint8).reshape(B_img.size[1], B_img.size[0], 3)

            A_parsing_path = self.parsing_paths[self.class_A_idx][index_A]
            A_parsing = Image.open(A_parsing_path).convert('L')
            A_parsing = np.array(A_parsing.getdata(), dtype=np.uint8).reshape(A_parsing.size[1], A_parsing.size[0], 1)
            A_img = self.mask_image(A_img, A_parsing)

            B_parsing_path = self.parsing_paths[self.class_B_idx][index_B]
            B_parsing = Image.open(B_parsing_path).convert('L')
            B_parsing = np.array(B_parsing.getdata(), dtype=np.uint8).reshape(B_parsing.size[1], B_parsing.size[0], 1)
            B_img = self.mask_image(B_img, B_parsing)

            # numpy conversions are an annoying hack to form a PIL image with more than 3 channels
            A_img = self.transform(A_img)
            B_img = self.transform(B_img)

            return {'A': A_img, 'B': B_img,
                    "A_class": self.class_A_idx, "B_class": self.class_B_idx,
                    'A_paths': A_img_path, 'B_paths': B_img_path}

        else:  # in test mode, load one image from each class
            i = self.class_counter % self.numClasses
            self.class_counter += 1
            # if self.get_samples:
            #     ind = random.randint(0, self.sizes[i] - 1)
            # else:
            ind = self.img_counter if self.img_counter < self.sizes[i] else -1
            if i == self.numClasses - 1:
                self.img_counter += 1

            if ind > -1:
                valid = True
                paths = self.img_paths[i][ind]
                img = Image.open(self.img_paths[i][ind]).convert('RGB')
                img = np.array(img.getdata(), dtype=np.uint8).reshape(img.size[1], img.size[0], 3)

                parsing_path = self.parsing_paths[i][ind]
                parsing = Image.open(parsing_path).convert('L')
                parsing = np.array(parsing.getdata(), dtype=np.uint8).reshape(parsing.size[1], parsing.size[0], 1)
                img = self.mask_image(img, parsing)

                img = self.transform(img)

            else:
                img = torch.zeros(3, self.opt.fineSize, self.opt.fineSize)
                paths = ''
                valid = False

            return {'Imgs': img,
                    'Paths': paths,
                    'Classes': i,
                    'Valid': valid}

    def __len__(self):
        if self.opt.isTrain:
            return round(sum(self.sizes) / 2)  # this determines how many iterations we make per epoch
        else:
            return max(self.sizes) * self.numClasses

    def name(self):
        return 'MulticlassUnalignedDataset'