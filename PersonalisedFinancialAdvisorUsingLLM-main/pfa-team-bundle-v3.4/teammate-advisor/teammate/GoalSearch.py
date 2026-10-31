

# Remove sg, pathList, A, T from the arguments for faster running.
# Best possible path algorithm is something else. Putting a reward for each
# step shall define the best possible way.
# pathList will contain the answer after the return.
GOAL_REACHED = 1
GOAL_NOT_REACHABLE = 2
GOAL_NOT_YET_REACHED = 3


class GoalSearch():

    def __init__(self, goalState, actionSpace,
                 transitionFunction, isGoalReachedFunction):
        self.sg = goalState
        self.pathList = []
        self.A = actionSpace
        self.T = transitionFunction
        self.isGR = isGoalReachedFunction
        self.st = GOAL_NOT_YET_REACHED
        self.s = None
    def BruteForce(self, s):
        isgr = self.isGR(s, self.sg)
        if GOAL_NOT_YET_REACHED == isgr:
            for a in self.A:
                (sNext, c) = self.T(s, a)
                if (GOAL_REACHED == self.BruteForce(sNext)):
                    self.pathList.insert(0, ((a, c), sNext))
                    return GOAL_REACHED
            return GOAL_NOT_REACHABLE
        return isgr
    def BestSearch1(self, s):
        stack = []
        a = 0
        while True:
            sNext = self.T(s, a)
            isgr = self.isGR(sNext, self.sg)
            if (GOAL_NOT_YET_REACHED == isgr):
                stack.append((a, sNext))
                s = sNext
                a = 0
            elif (GOAL_NOT_REACHABLE == isgr):
                a = a + 1
                if a >= len(self.A):
                    if stack:                        
                        a, _ = stack.pop()
                        a = a + 1
                        _, s = stack[-1]
                    else:
                        break
                else:
                    # Do not change s
                    pass        
            else:
                stack.append((a, sNext))
                break           
            
            return isgr
        
    def BestSearch2(self, s):
        self.s = s
        stack = []
        a = 0
        
        stackLongest = []
        lengthLongest = 0
        oldSt = GOAL_NOT_YET_REACHED
        
        while True:
            sNext, c = self.T(self.s, self.A[a])
            presentSt = self.isGR(sNext, self.sg)
            if (GOAL_NOT_YET_REACHED == presentSt):
                stack.append(((a, c), sNext))
                self.s = sNext
                a = 0
            elif (GOAL_NOT_REACHABLE == presentSt):
                a = a + 1
                if a >= len(self.A):
                    if stack:
                        ((a, _), _) = stack.pop()
                        a = a + 1
                        
                        if stack:
                            ((_, _), self.s) = stack[-1]
                        else:
                            self.s = s
                            break
                    else:
                        break
                else:
                    if GOAL_NOT_YET_REACHED == oldSt:
                        if lengthLongest < self.s.balance:
                            lengthLongest = self.s.balance
                            stackLongest = stack.copy()
            else:
                stack.append(((a, c), sNext))
                stackLongest = stack.copy()
                break
            oldSt = presentSt
        self.pathList = stackLongest.copy()
        return presentSt
            
            
    def BestSearch(self, s):
        self.s = s.copy()
        if GOAL_NOT_REACHABLE == self.BruteForce(s):
            m = 0
            aM = None
            for a in self.A:
                (sNext, c) = self.T(s, a)
                if (m < sNext.balance) and (
                        (self.sg.time - sNext.time).days > 0):
                    m = sNext.balance
                    aM = a
                    sNextM = sNext
                    cM = c
            if aM is not None:
                self.pathList.append(((aM, cM), sNextM))
            self.st = GOAL_NOT_REACHABLE    
            return GOAL_NOT_REACHABLE
        else:
            self.st = GOAL_REACHED
            return GOAL_REACHED

    def getFinalList(self):
        if(self.st == GOAL_REACHED):
            return (self.pathList, 0)
        else:
            if self.pathList == []:
                return (self.pathList, (self.sg.balance - self.s.balance))
            else:
                return (self.pathList, (self.sg.balance - ((self.pathList[-1])[1].balance)))