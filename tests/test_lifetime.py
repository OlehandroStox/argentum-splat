"""A destroyed native wrapper must not keep millions of splats alive."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_native_actions import function


class LifetimeTests(unittest.TestCase):
    def test_release_drops_owned_data_but_never_mutates_shared_buffers(self):
        shared=[1,2,3]
        cache={'same':shared,'unrelated':[4]}
        state=SimpleNamespace(load_key='same',cloud=shared,prepared=shared,
            spatial=shared,colors=shared,mesh_template=object(),ready_request=object(),
            blocked_request=object(),queued_request=object(),source_analysis=object(),
            display_key=object(),job={'worker_inputs':shared})
        invalidate=function('plugin.py','invalidate',{},'SplatObject')
        state.invalidate=lambda:invalidate(state)
        release=function('plugin.py','release_transient_data',{'CLOUD_CACHE':cache},'SplatObject')
        release(state)
        for name in ('cloud','prepared','spatial','colors','mesh_template','ready_request',
                     'blocked_request','queued_request','source_analysis','display_key'):
            self.assertIsNone(getattr(state,name))
        self.assertEqual(cache,{'unrelated':[4]})
        self.assertEqual(shared,[1,2,3])
        self.assertIs(state.job['worker_inputs'],shared)
        release(state)  # repeated timer cleanup is harmless

    def test_free_releases_idle_data_and_queues_worker_cancellation(self):
        pending=[];event=Mock()
        free=function('plugin.py','Free',dict(PENDING=pending,
            I=SimpleNamespace(CANCEL=10,MESSAGE_ID=11),
            c4d=SimpleNamespace(SpecialEventAdd=event)),'SplatObject')
        state=SimpleNamespace(release_transient_data=Mock(),job=None)
        free(state,object())
        state.release_transient_data.assert_called_once()
        self.assertEqual(pending,[])
        state.job={'worker':object()}
        free(state,object())
        self.assertEqual(pending,[(state,10)])
        event.assert_called_once_with(11)


if __name__=='__main__':unittest.main()
