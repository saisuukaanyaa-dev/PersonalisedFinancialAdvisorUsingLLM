# Remove sg, pathList, A, T from the arguments for faster running.
# Best possible path algorithm is something else. Putting a reward for each
# step shall define the best possible way.
# pathList will contain the answer after the return.
GOAL_NOT_REACHABLE = 2
GOAL_NOT_YET_REACHED = 3


class GoalSearch:
    def __init__(self, goalState, actionSpace,
                 transitionFunction, isGoalReachedFunction):
        self.sg = goalState
        self.pathList = []
        self.A = actionSpace
        self.T = transitionFunction
        self.isGR = isGoalReachedFunction
        self.st = GOAL_NOT_YET_REACHED
        self.s = None

    def BestSearch(self, s):
        self.s = s.copy()
        stack = []
        a = 0

        stackLongest = []
        lengthLongest = 0
        oldSt = GOAL_NOT_YET_REACHED
        if len(self.A) == 0:
            self.pathList = stackLongest.copy()
            return GOAL_NOT_REACHABLE
        while True:
            sNext, c = self.T(self.s, self.A[a])
            presentSt = self.isGR(sNext, self.sg)
            if (GOAL_NOT_YET_REACHED == oldSt
                    and GOAL_NOT_REACHABLE == presentSt):
                oldSt = presentSt
                if lengthLongest < self.s.balance:
                    lengthLongest = self.s.balance
                    stackLongest = stack.copy()

            if GOAL_NOT_YET_REACHED == presentSt:
                stack.append(((a, c), sNext))
                self.s = sNext.copy()
                a = 0
            else:
                a = a + 1
                while a >= len(self.A):
                    if stack:
                        ((a, _), _) = stack.pop()
                        a = a + 1
                    else:
                        self.pathList = stackLongest.copy()
                        return presentSt

                if stack:
                    self.s = stack[-1][1].copy()
                else:
                    self.s = s.copy()
            oldSt = presentSt
        self.pathList = stackLongest.copy()
        return presentSt

    def getFinalList(self):
        if self.pathList == []:
            return (self.pathList, self.sg.balance - self.s.balance)
        else:
            return (self.pathList,
                    self.sg.balance - self.pathList[-1][1].balance)
