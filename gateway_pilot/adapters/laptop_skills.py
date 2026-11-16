"""Reviewed local-only provider for laptop Skill deployment v1."""
from types import MappingProxyType

from .bindings import require
from .linux_wifi import LinuxWifiBackend
from .read_backends import observations


class LaptopSkillBackend(LinuxWifiBackend):
    revision = '2.0.0'
    source = 'linux_client/skill_laptop_v1'
    probe_ids = MappingProxyType({**LinuxWifiBackend.probe_ids,
                                  'expansion.client_association':'probe.linux.client_association'})

    def supports(self, fid, context):
        if fid == 'expansion.client_association':
            if not super().supports('laptop.wifi', context):
                return False
            wifi = self.wifi()
            return not wifi['associated'] or bool(wifi['bssid'])
        return super().supports(fid, context)

    def sample(self, function, arguments, context):
        if function['function_id'] != 'expansion.client_association':
            return super().sample(function, arguments, context)
        require(self.supports(function['function_id'], context), 'laptop_association_unavailable')
        wifi = self.wifi()
        require(context.environment_id == self.environment_id, 'laptop_association_context_changed')
        return observations(function, {'expansion.client_association':{
            'associated':wifi['associated'], 'access_point_id':wifi['bssid'] if wifi['associated'] else ''}},
            self.source, context)
