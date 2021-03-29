from loguru import logger
import ringmaster.cloudflare as cf

testdata_origin_ca_match = [
    {
      "hostnames": [
        "example.com",
        "*.example.com"
      ],
    },

    # should be left alone
    {
        "hostnames": [
            "foo.example.com",
            "*.foo.example.com"
        ],
    }
]

testdata_origin_ca_no_match = [
    {
      "hostnames": [
        "foo.com",
        "*.foo.com"
      ],
    },

    # should be left alone
    {
        "hostnames": [
            "foo.example.com",
            "*.foo.example.com"
        ],
    }
]


# https://api.cloudflare.com/#origin-ca-list-certificates
def test_origin_ca_list_contains_hostname():
    target_hostname = "example.com"

    def hostname_filter(data):
        return cf.list_contains_dict_value(data, "hostnames", target_hostname)

    assert len(list(filter(hostname_filter, testdata_origin_ca_match))) == 1
    assert len(list(filter(hostname_filter, testdata_origin_ca_no_match))) == 0


def test_csr():
    csr, private_key = cf.create_csr("foo.com")
    logger.debug(csr)
    logger.debug(private_key)
    assert len(csr) > 0
    assert len(private_key) > 0
