from typing import Iterable, Optional, Callable


class ReducerFilter:
    """Class to except empty and unvanted strings from parsed picture descriptions"""
    def __init__(self):
        self.uniques = []
        self.filter_vals = [[], [''], 'Unknown', None]
        self.reduced_copy = {}

    @staticmethod
    def optional_filter(to_filter: list, blacklist: Iterable) -> list[str]:
        """filers value by blacklist if it was passed"""
        if blacklist and to_filter:
            return list(x for x in to_filter if x not in blacklist)
        elif to_filter:
            return to_filter
        else:
            return []

    def general_empty_filter(self, parsed_taglist: list) -> list[str]:
        """filters various empty walues such as None, [], '', etc"""
        return [x for x in parsed_taglist if x not in self.filter_vals]


class ReduceMethod:
    """Class which represented method for filtering, based on how much results were parsed"""
    def __init__(self, single_method: Callable, common_method: Callable, i: Optional = 0,
                 special: Optional = None, condition: Optional[Callable] = False):
        self.single_method = single_method
        self.common_method = common_method
        self.special = special
        self.condition = condition
        self.i = i

    def standart_methods(self, to_reduce: list) -> list[str]:
        """filters input iterable depending on how much sub-iterables it have"""
        if self.i == 1:
            return self.single_method(to_reduce)
        else:
            return self.common_method(to_reduce)

    def apply_method(self, to_reduce: list) -> list[str]:
        """
        Provides ability to pass special condition of redusing.
        If condition != True, self.standart methods would be applyed

        """
        if self.special and self.condition(to_reduce):
            special_method_result = self.special(to_reduce)
            if special_method_result:
                return special_method_result
            else:
                return self.standart_methods(to_reduce)
        else:
            return self.standart_methods(to_reduce)


class PositionalReduce:
    """Applyes chosen metod for flatten lists with parsed descriptions, dependin on the cathegory of parsed desc"""
    def __init__(self, method: ReduceMethod, pos_val: list):
        self.method = method
        self.pos_val = pos_val
        self.filter = ReducerFilter()

    def self_check(self):
        if not self.pos_val:
            pass
        else:
            self.pos_val = self.filter.general_empty_filter(self.pos_val)
            self.method.i = len(self.pos_val)

    def reduce(self) -> list[str]:
        self.self_check()
        return self.method.apply_method(self.pos_val)
