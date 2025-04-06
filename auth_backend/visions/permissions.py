# permissions.py
from rest_framework import permissions
from .models import OpenSourceVisionRequest, CodeChangeProposal

class IsProjectCollaboratorOrOwner(permissions.BasePermission):
    """
    Allows access only to the project owner or approved collaborators.
    Assumes the view has `self.kwargs['pk']` or similar for project ID,
    or that the object being checked is the OpenSourceVisionRequest itself.
    """
    message = "You do not have permission to access or modify this project's collaborative code."

    def has_object_permission(self, request, view, obj):
        # Ensure the object being checked is the OpenSourceVisionRequest
        if not isinstance(obj, OpenSourceVisionRequest):
            # If checking against CollaborativeCode, access its project link
            try:
                 project = obj.project
            except AttributeError:
                 # Cannot determine project from object, deny access
                 # Or, modify view to pass project explicitly to check_object_permissions
                 return False
        else:
            project = obj

        # Allow owner
        if project.creator == request.user:
            return True
        # Allow collaborators
        if request.user in project.collaborators.all():
            return True
        return False

class IsProposalOwner(permissions.BasePermission):
    """ Allows access only if the user is the proposer of the CodeChangeProposal. """
    def has_object_permission(self, request, view, obj):
        return obj.proposer == request.user

class IsProjectOwnerForProposal(permissions.BasePermission):
    """ Allows access only if the user is the owner of the project linked to the proposal. """
    def has_object_permission(self, request, view, obj):
        # Assumes obj is CodeChangeProposal
        return obj.project.creator == request.user