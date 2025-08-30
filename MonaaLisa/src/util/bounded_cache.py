from collections import OrderedDict
import os


class BoundedEmbeddingCache:
    
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def __setitem__(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
        self.cache[key] = value
    
    def update(self, other_dict):
        for key, value in other_dict.items():
            self[key] = value
    
    def copy(self):
        return dict(self.cache)
    
    def __len__(self):
        return len(self.cache)
    
    def clear(self):
        self.cache.clear()
